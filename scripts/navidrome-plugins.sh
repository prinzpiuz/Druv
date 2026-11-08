#!/usr/bin/env bash
# Keeps a Navidrome plugins folder in step with arr/navidrome/plugins.txt.
#
#   navidrome-plugins.sh sync                  install, update and remove plugins
#   navidrome-plugins.sh add <repo-url> <tag> [asset] [installed-name]
#                                              download once, print the sha256 and
#                                              append a pinned line to plugins.txt
#   navidrome-plugins.sh check                 list plugins with a newer release
#
# The navidrome-plugins container runs `sync` before Navidrome starts. `add` and
# `check` are for the owner and need bash, curl, jq and sha256sum.
set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
PLUGINS_FILE=${PLUGINS_FILE:-$script_dir/../arr/navidrome/plugins.txt}
PLUGINS_DIR=${PLUGINS_DIR:-/configs/navidrome/plugins}
# Owner for installed files when the script runs as root (the container does).
PLUGINS_OWNER=${PLUGINS_OWNER:-1000:1000}
# Lists the files this script installed, so it never deletes a plugin that was
# copied in by hand.
MANAGED_FILE=".managed-by-navidrome-plugins"

success_log() { echo "[navidrome-plugins] OK: $*"; }
warning_log() { echo "[navidrome-plugins] WARNING: $*" >&2; }
error_log() { echo "[navidrome-plugins] ERROR: $*" >&2; }

usage() {
	sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
	exit 2
}

# https://github.com/owner/repo(.git)(/) -> owner/repo
repo_from_url() {
	local repo=${1#https://github.com/}
	repo=${repo%/}
	repo=${repo%.git}
	if [[ ! $repo =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
		error_log "not a GitHub repository URL: $1"
		return 1
	fi
	echo "$repo"
}

github_api() {
	local auth=()
	if [[ -n ${GITHUB_TOKEN:-} ]]; then
		auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
	fi
	curl -fsSL --retry 3 -H "Accept: application/vnd.github+json" "${auth[@]}" \
		"https://api.github.com/$1"
}

file_sha256() { sha256sum "$1" | cut -d ' ' -f 1; }

# "release.ndp" or "release.ndp=installed.ndp" -> sets src and dest.
# Navidrome uses the file name as the plugin ID, so some plugins must be saved
# under a name other than the one in the release.
split_asset() {
	src=${1%%=*}
	dest=${1#*=}
	local name
	for name in "$src" "$dest"; do
		if [[ $name != *.ndp || $name == */* || $name == *=* ]]; then
			error_log "asset must be a .ndp file name, or release.ndp=installed.ndp: $1"
			return 1
		fi
	done
}

# Prints "url tag asset sha256" for each entry; sha256 may be empty.
read_entries() {
	if [[ ! -f $PLUGINS_FILE ]]; then
		error_log "plugins file not found: $PLUGINS_FILE"
		return 1
	fi
	local url tag asset sha extra
	while read -r url tag asset sha extra || [[ -n $url ]]; do
		[[ -z $url || $url == \#* ]] && continue
		if [[ -z $tag || -z $asset || -n $extra ]]; then
			error_log "bad line in plugins.txt: $url $tag $asset $sha $extra"
			return 1
		fi
		echo "$url $tag $asset ${sha:-}"
	done <"$PLUGINS_FILE"
}

sync_plugins() {
	local status=0 entries url tag asset expected repo digest target tmp actual src dest
	local -a wanted=()
	entries=$(read_entries)
	mkdir -p "$PLUGINS_DIR"
	touch "$PLUGINS_DIR/$MANAGED_FILE"

	while read -r url tag asset expected; do
		[[ -z $url ]] && continue
		repo=$(repo_from_url "$url") || {
			status=1
			continue
		}
		split_asset "$asset" || {
			status=1
			continue
		}
		wanted+=("$dest")
		target="$PLUGINS_DIR/$dest"

		if [[ -z $expected ]]; then
			if ! digest=$(github_api "repos/$repo/releases/tags/$tag" |
				jq -r --arg a "$src" '.assets[] | select(.name == $a) | .digest // empty'); then
				warning_log "cannot reach GitHub for $src; keeping the installed copy"
				continue
			fi
			if [[ $digest != sha256:* ]]; then
				error_log "$repo $tag has no $src, or GitHub gives no digest for it. Pin a sha256 in plugins.txt."
				status=1
				continue
			fi
			expected=${digest#sha256:}
			warning_log "$src is not pinned; trusting GitHub's digest $expected. Run 'add' to pin it."
		fi

		if [[ -f $target && $(file_sha256 "$target") == "$expected" ]]; then
			success_log "$dest $tag is up to date"
			continue
		fi

		# Not .ndp, so Navidrome ignores the partial file during the download.
		tmp=$(mktemp "$PLUGINS_DIR/.download.XXXXXX")
		if ! curl -fsSL --retry 3 -o "$tmp" \
			"https://github.com/$repo/releases/download/$tag/$src"; then
			rm -f "$tmp"
			warning_log "download failed for $src $tag; keeping the installed copy"
			continue
		fi
		actual=$(file_sha256 "$tmp")
		if [[ $actual != "$expected" ]]; then
			rm -f "$tmp"
			error_log "checksum mismatch for $src $tag: expected $expected, got $actual"
			status=1
			continue
		fi
		chmod 644 "$tmp"
		[[ $(id -u) -eq 0 ]] && chown "$PLUGINS_OWNER" "$tmp"
		mv -f "$tmp" "$target"
		if [[ $src == "$dest" ]]; then
			success_log "installed $dest $tag"
		else
			success_log "installed $src $tag as $dest"
		fi
	done <<<"$entries"

	# A failed entry may be a typo in a line that should stay, so delete nothing
	# until every entry succeeds.
	if [[ $status -ne 0 ]]; then
		warning_log "errors above; not removing any plugins this run"
		return "$status"
	fi

	# Remove plugins this script installed that are no longer listed.
	local old keep w
	while read -r old; do
		[[ -z $old ]] && continue
		keep=false
		for w in "${wanted[@]}"; do
			[[ $w == "$old" ]] && keep=true
		done
		if [[ $keep == false && -f $PLUGINS_DIR/$old ]]; then
			rm -f "$PLUGINS_DIR/$old"
			success_log "removed $old (no longer in plugins.txt)"
		fi
	done <"$PLUGINS_DIR/$MANAGED_FILE"
	printf '%s\n' "${wanted[@]}" >"$PLUGINS_DIR/$MANAGED_FILE"

	return "$status"
}

add_plugin() {
	local url=${1:-} tag=${2:-} asset=${3:-} install_name=${4:-} repo release names count tmp sha digest
	local entry_name src dest
	[[ -z $url || -z $tag ]] && usage
	repo=$(repo_from_url "$url")
	release=$(github_api "repos/$repo/releases/tags/$tag")
	if [[ -z $asset ]]; then
		names=$(jq -r '.assets[].name | select(endswith(".ndp"))' <<<"$release")
		count=$(grep -c . <<<"$names" || true)
		if [[ $count -ne 1 ]]; then
			error_log "$repo $tag has $count .ndp files. Pass the asset name:"
			echo "$names" >&2
			return 1
		fi
		asset=$names
	fi
	entry_name=$asset
	[[ -n $install_name ]] && entry_name="$asset=$install_name"
	split_asset "$entry_name"
	if read_entries | awk '{ n = $3; sub(/.*=/, "", n); print n }' | grep -qxF "$dest"; then
		error_log "$dest is already in $PLUGINS_FILE"
		return 1
	fi

	tmp=$(mktemp)
	trap 'rm -f "$tmp"' RETURN
	curl -fsSL --retry 3 -o "$tmp" "https://github.com/$repo/releases/download/$tag/$asset"
	sha=$(file_sha256 "$tmp")
	digest=$(jq -r --arg a "$asset" '.assets[] | select(.name == $a) | .digest // empty' <<<"$release")
	if [[ -n $digest && $digest != "sha256:$sha" ]]; then
		error_log "download does not match GitHub's digest ($digest)"
		return 1
	fi

	printf '%s  %s  %s  %s\n' "https://github.com/$repo" "$tag" "$entry_name" "$sha" >>"$PLUGINS_FILE"
	success_log "added $entry_name $tag ($sha) to $PLUGINS_FILE"
	echo "Review the plugin's permissions, commit plugins.txt and redeploy."
}

check_plugins() {
	local url tag asset sha repo latest entries
	entries=$(read_entries)
	while read -r url tag asset sha; do
		[[ -z $url ]] && continue
		repo=$(repo_from_url "$url")
		if ! latest=$(github_api "repos/$repo/releases/latest" | jq -r '.tag_name'); then
			warning_log "cannot read the latest release of $repo"
			continue
		fi
		if [[ $latest == "$tag" ]]; then
			success_log "$asset $tag is the latest release"
		else
			echo "[navidrome-plugins] UPDATE: $asset $tag -> $latest (https://github.com/$repo/releases/tag/$latest)"
		fi
	done <<<"$entries"
}

case ${1:-} in
sync) sync_plugins ;;
add)
	shift
	add_plugin "$@"
	;;
check) check_plugins ;;
*) usage ;;
esac
