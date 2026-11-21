# linkding (bookmarks)

[linkding](https://github.com/sissbruecker/linkding) is a self-hosted bookmark manager. It replaces Raindrop.io here, because Raindrop does not load on some Indian ISPs. linkding runs in the tools stack on port 9090, and Caddy publishes it at https://bookmarks.prinzpiuz.in. Its data (an SQLite database) is in `/configs/linkding`, which Backrest backs up.

## What moves from Raindrop, and what does not

| Raindrop | linkding |
|---|---|
| Bookmarks, titles, dates added | Kept |
| Tags | Kept. Spaces become `-`, as linkding tags cannot have spaces. |
| Collections (folders) | linkding has no folders. `raindrop_to_linkding.py` turns each collection into a tag. A bookmark in `Dev / Python` gets `dev` and `python`. |
| Excerpt or note | Kept as the description |
| Unsorted | No tag |
| Trash | Left out |
| Highlights, covers, permanent copies | Not moved |

To get back a collection view, make a **bundle** in linkding: a saved search, for example all bookmarks with the tag `dev`. Use Bundles menu > Manage bundles in the sidebar.

## Migration plan

### 1. Deploy linkding

1. In Cloudflare, add a DNS record for `bookmarks.prinzpiuz.in`, the same as the other public subdomains. Skip this step if a wildcard record exists.
2. In `tools/.env`, set `LINKDING_SUPERUSER_NAME` and a strong `LINKDING_SUPERUSER_PASSWORD`. The login page is public.
3. `cd tools && docker compose up -d linkding`
4. Merging the PR deploys the new Caddy site, as for other template changes.
5. Open http://<homelab-ip>:9090 and log in. Then open https://bookmarks.prinzpiuz.in on mobile data to check the public URL.

### 2. Export from Raindrop

In the Raindrop web app: Settings > Backups > Create new. Raindrop emails you when the backup is ready. Download the **HTML** file from the same page.

### 3. Convert the export

```bash
python3 tools/linkding/raindrop_to_linkding.py ~/Downloads/raindrop.html ~/Downloads/linkding.html
```

It prints the number of bookmarks written. `--skip-folder NAME` (repeatable) gives the named collections no tag. The default is `Unsorted` and `Trash`.

### 4. Import

linkding > Settings > General > Import: choose `linkding.html`, then Import. Use the LAN URL (`http://<homelab-ip>:9090`) for a large file, so the upload does not go through the VPS.

All imported bookmarks are private. A second import of the same file updates bookmarks with the same URL. It does not make duplicates.

### 5. Check

- The bookmark count in linkding matches the count the script printed.
- Spot-check a few bookmarks from deep collections for their tags.
- Make bundles for the collections you use most.

### 6. Set up your devices

- **Browser:** the linkding extension for [Firefox](https://addons.mozilla.org/firefox/addon/linkding-extension/) or [Chrome](https://chrome.google.com/webstore/detail/linkding-extension/beakmhbijpdhipnjhnclmhgjlddhidpe). It needs the URL `https://bookmarks.prinzpiuz.in` and an API token from Settings > Integrations > REST API > Create API token.
- **Android:** [Linkdy](https://play.google.com/store/apps/details?id=com.jgeek00.linkdy) (Play Store) or [LinkBuddy](https://github.com/peterto/LinkBuddy/releases). Both use the same URL and an API token. Other apps are listed in the [linkding community page](https://github.com/sissbruecker/linkding/blob/master/docs/src/content/docs/community.md).
- Remove the Raindrop extension and app, so new bookmarks go only to linkding.

### 7. Retire Raindrop

Use only linkding for one or two weeks. Keep the Raindrop HTML export file as an extra backup. Then cancel Raindrop Pro, if you pay for it, and delete the account.

## HTML snapshots (optional)

The `-plus` image saves a copy of each new page, using a headless Chromium. This is like Raindrop's permanent copies. To turn it on, set `LINKDING_VERSION=1.47.0-plus` in `version.env` and recreate the container. The image is much larger, and each save uses some CPU and memory.
