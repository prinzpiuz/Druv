```
                         ____
                        |  _ \ _ __ _   ___   __
                        | | | | '__| | | \ \ / /
                        | |_| | |  | |_| |\ V /
                        |____/|_|   \__,_| \_/  v3.0
                         Setup Scripts For A Media Server

```
* **Create .env file**

  `cp env.sample .env`

* **Start Services**

  `docker-compose --env-file=.env up -d`

* **Container IP Address**

  `docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <Container Name>`


### Usefull Links

* [Inter Container Networking](https://github.com/qdm12/gluetun-wiki/blob/main/setup/inter-containers-networking.md)
