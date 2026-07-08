# Logstash boilerplate

This repository contains a boilerplate for deploying logstash on Scalingo.

> **⚠️ Setup Pass Emploi (≠ boilerplate ci-dessous).** On ne tourne PLUS en
> mono-pipeline `-f logstash.conf`. L'ingestion est découplée en **2 pipelines**
> (`config/pipelines.yml`) pour que l'ACK du drain ne dépende ni des filtres ni d'ES
> (évite la quarantaine Scalingo — cf. [`../docs/blackout-logs/`](../docs/blackout-logs/README.md)) :
> - **`ingest.conf`** — `http input → pipeline output`, 0 filtre, file mémoire (ACK rapide).
> - **`process.conf`** — `pipeline input → filtres ECS → Elasticsearch`, `queue.type: persisted` (filet backpressure ES).
>
> Le `Procfile` lance donc `bin/logstash` **sans `-f`** (sinon `pipelines.yml` est
> ignoré). La section boilerplate ci-dessous est conservée à titre de référence
> upstream.

You have three different configuration available:

* `logstash.conf`: this configuration will listen for http request
  authenticated by the authentication information passed in the `USER` and
  `PASSWORD` environment variables and send it to and elasticsearch database.
  This will also parse url defined variables.
* `logstash-json.conf` this configuration is based on the previous one but if
  the content is a valid json it will parse it
* `logstash-kv.conf` this configuration is based on `logstash.conf` but it will
  also parse the content to search and parse patterns like `key=value`

By default we are using the `logstash.conf` configuration, but you can use
another one by changing the `web` process of the `Procfile` from: ``` web:
bin/logstash -f logstash.conf ```

To:
```
web: bin/logstash -f logstash-json.conf
```

To:
```
web: bin/logstash -f logstash-kv.conf
```

## Configuration

You will need to configure the following environment variables:

* `USER` the username that you will use to authenticate against your logstash
  instance
* `PASSWORD` the password that you will use to authenticate against your
  logstash instance
* `ELASTICSEARCH_URL` the URL of your elasticsearch instance. (If you use our
  Elasticsearch addon, this will be automatically added)

You will also change the `change-me` index name in the output section of your
logstash configuration.

## Updating Logstash version

To update your application with a more recent version of version of **Logstash**,
the most straightforward method is to deploy your application. The
[used buildpack](https://github.com/Scalingo/logstash-buildpack) is defining the
[used version](https://github.com/Scalingo/logstash-buildpack/blob/master/bin/compile#L9),
which can be overrided with the environment variable `LOGSTASH_VERSION`.

To trigger the new deployment, either use:

- The *Manual Deployment* feature of our GitHub or Gitlab
- `git push` deployment after adding an empty commit to your project:
  `git commit --allow-empty -m "New deployment to update logstash"`
