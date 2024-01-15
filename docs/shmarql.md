# Viewing the Data in a triplestore

It is possible to view the Viewsari data in a Shmarql triplestore, by running the following command in the root of this repository:

```shell
docker-compose up
```

This should start up a Shmarql instance, load in all the .ttl files found in the /data/ directory.

You can view the data on: http://127.0.0.1:9000/shmarql

For example, [Volume 1](http://127.0.0.1:9000/shmarql?s=%3Chttp%3A//viewsari.github.io/ontology%23volume1%3E)
