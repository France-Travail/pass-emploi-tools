#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOOLS_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
WORKSPACE=${WORKSPACE:-$(dirname "$(git -C "$SCRIPT_DIR" rev-parse --path-format=absolute --git-common-dir | xargs dirname)")}
SORTIE="$SCRIPT_DIR/sortie"
FETCH=true
TENTATIVES=8
ATTENTE_QUOTA=15
REGIONS=(osc-fr1 osc-secnum-fr1)
REPOS=(pass-emploi-api pass-emploi-web pass-emploi-connect pass_emploi_app pass-emploi-auth pass-emploi-analytics pass-emploi-tools)

SOURCES=$(cat <<'EOF'
api	pass-emploi-api	.
web	pass-emploi-web	.
connect	pass-emploi-connect	.
keycloak	pass-emploi-auth	.
terraform-keycloak	pass-emploi-auth	config/terraform
vault-ansible	pass-emploi-auth	config/vault
tfstate	pass-emploi-auth	-
app-mobile	pass_emploi_app	.
analytics	pass-emploi-analytics	.
tools	pass-emploi-tools	.
logstash	pass-emploi-tools	logs
logstash-process	pass-emploi-tools	logs
elastic-agent	pass-emploi-tools	elastic-agent
heartbeat	pass-emploi-tools	heartbeat
metabase	pass-emploi-tools	stats
nginx-rp	pass-emploi-tools	proxy
gatling	pass-emploi-tools	perf
mock-externes	pass-emploi-tools	perf/mock-externes
EOF
)

DEPUIS=
SIMULER=false
ENVOYER=false
DATA_STREAM=logs-alertes-versions-default
EOL_API=https://endoflife.date/api/v1/products

usage() {
  cat <<EOF
Usage : $(basename "$0") [--sortie DIR] [--sans-fetch] [--depuis FICHIER] [--simuler | --envoyer]

Produit l'inventaire des versions Pass Emploi (Scalingo ${REGIONS[*]} + repos de $WORKSPACE)
dans DIR/inventaire.json et DIR/inventaire.md (défaut : $SORTIE), avec les fins de vie
lues sur endoflife.date.

  --depuis FICHIER  repart d'un inventaire.json existant, sans Scalingo ni repos :
                    recalcule les fins de vie, le markdown et les documents d'alerte
  --simuler         écrit le corps _bulk des documents d'alerte dans DIR/alertes-versions.ndjson
  --envoyer         idem, puis l'envoie à $DATA_STREAM
                    (ELASTIC_URL et ELASTIC_ALERTES_VERSIONS_API_KEY requises)

Version du cluster Elastic Cloud : lue si ELASTIC_URL et ELASTIC_INVENTAIRE_API_KEY sont définies
(clé API limitée au privilège cluster monitor).
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --sortie) SORTIE=$2; shift 2 ;;
    --sans-fetch) FETCH=false; shift ;;
    --depuis) DEPUIS=$2; shift 2 ;;
    --simuler) SIMULER=true; shift ;;
    --envoyer) ENVOYER=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

log() { printf '%s\n' "$*" >&2; }

prerequis=(jq git curl)
[ -n "$DEPUIS" ] || prerequis+=(scalingo)
for outil in "${prerequis[@]}"; do
  command -v "$outil" >/dev/null || { log "Prérequis manquant : $outil"; exit 1; }
done
if $ENVOYER && { [ -z "${ELASTIC_URL:-}" ] || [ -z "${ELASTIC_ALERTES_VERSIONS_API_KEY:-}" ]; }; then
  log "--envoyer : ELASTIC_URL et ELASTIC_ALERTES_VERSIONS_API_KEY sont requises"
  exit 1
fi
if [ -n "$DEPUIS" ] && ! jq -e '.faits and .matrice and .stackElastic' "$DEPUIS" >/dev/null 2>&1; then
  log "--depuis : $DEPUIS n'est pas un inventaire.json"
  exit 1
fi

TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT
mkdir -p "$TRAVAIL/apps" "$SORTIE"
: >"$TRAVAIL/erreurs.tsv"

scalingo_lecture() {
  local region=$1 commande=$2
  shift 2
  case "$commande" in
    whoami|apps|apps-info|addons|addons-info|ps|env|deployments|deployment-logs|integration-link|stacks) ;;
    *) log "Commande Scalingo refusée (lecture seule) : $commande"; exit 1 ;;
  esac
  local sortie code tentative
  for tentative in $(seq 1 "$TENTATIVES"); do
    code=0
    sortie=$(scalingo --region "$region" "$commande" "$@" </dev/null 2>/dev/null) || code=$?
    if [ "$code" -eq 0 ]; then
      sed 's/\x1b\[[0-9;]*m//g' <<<"$sortie"
      return 0
    fi
    case "$sortie" in
      *tokens/exchange*) sleep "$ATTENTE_QUOTA" ;;
      *) break ;;
    esac
  done
  printf '%s\t%s\t%s\n' "$region" "$commande" "$*" >>"$TRAVAIL/erreurs.tsv"
}

tableau_en_tsv() {
  grep '^│' | sed -E 's/^│ *//; s/ *│$//; s/ *│ */\t/g' || true
}

env_de_app() {
  local nom=$1 projet=$2
  case "$nom" in
    *-prod) echo prod ;;
    *-staging) echo staging ;;
    *-perf) echo perf ;;
    *) case "$projet" in */prod) echo prod ;; */staging) echo staging ;; */perf) echo perf ;; *) echo autre ;; esac ;;
  esac
}

composant_de_app() {
  local n=${1#pass-emploi-}
  n=${n%-prod}; n=${n%-staging}; n=${n%-perf}
  echo "$n"
}

versions_deployees() {
  sed -nE \
    -e 's/.*Downloading and installing node ([0-9][0-9.]*).*/node\t\1/p' \
    -e 's/.*Using yarn ([0-9][0-9.]*).*/yarn\t\1/p' \
    -e 's/.*Installing Azul Zulu OpenJDK ([0-9][0-9.]*).*/java\t\1/p' \
    -e 's/.*openjdk version "([0-9][0-9._]*)".*/java\t\1/p' \
    -e 's/.*Installing Logstash ([0-9][0-9.]*).*/logstash\t\1/p' \
    -e 's/.*Installing Elastic Agent ([0-9][0-9.]*).*/elastic-agent\t\1/p' \
    -e 's/.*Downloading Heartbeat version ([0-9][0-9.]*).*/heartbeat\t\1/p' \
    -e 's/.*Bundling Nginx ([0-9][0-9.]*).*/nginx\t\1/p' \
    -e 's#.*downloads\.metabase\.com/v([0-9][0-9.]*)/.*#metabase\t\1#p' \
    -e 's/.*Using keycloak version: ([0-9][0-9.]*).*/keycloak\t\1/p' \
    -e 's/.*(install of|Installing) Python ([0-9][0-9.]*).*/python\t\2/p' \
    -e 's/.*using Gradle ([0-9][0-9.]*).*/gradle\t\1/p' \
    -e 's#.*(Downloading|Cloning) custom buildpack:? (https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\#[A-Za-z0-9_./-]+)?).*#buildpack\t\2#p' \
    | sed -E 's/\.+$//' | sort -u
}

variables_de_version() {
  awk -F= '
    $1 ~ /^[A-Z0-9_]+_VERSION$/ {
      valeur = substr($0, length($1) + 2)
      if (valeur !~ /^[A-Za-z0-9._+-]{1,40}$/) valeur = "<valeur masquée : format inattendu>"
      print $1 "\t" valeur
    }
    $1 == "BUILDPACK_URL" { print "#BUILDPACK_URL\tdéfinie" }
    $1 == "PROJECT_DIR" { print "#PROJECT_DIR\tdéfinie" }
  '
}

collecter_app() {
  local region=$1 nom=$2 statut=$3 projet=$4
  local env composant stack addons conteneurs variables depot deploiement versions source_ligne
  env=$(env_de_app "$nom" "$projet")
  composant=$(composant_de_app "$nom")
  stack=$(scalingo_lecture "$region" apps-info --app "$nom" | tableau_en_tsv | awk -F'\t' '$1=="Stack"{print $2}')

  addons='[]'
  while IFS=$'\t' read -r fournisseur id plan statut_addon; do
    [ -n "${id:-}" ] || continue
    local info
    info=$(scalingo_lecture "$region" addons-info --app "$nom" "$id" | tableau_en_tsv)
    addons=$(jq -c \
      --arg fournisseur "$fournisseur" --arg plan "$plan" --arg statut "$statut_addon" \
      --arg type "$(awk -F'\t' '$1=="Database Type"{print $2}' <<<"$info")" \
      --arg version "$(awk -F'\t' '$1=="Version"{print $2}' <<<"$info")" \
      --arg maintenance "$(awk -F'\t' '$1=="Maintenance window"{print $2}' <<<"$info")" \
      '. + [{fournisseur: $fournisseur, type: $type, plan: $plan, statut: $statut, version: $version, maintenance: $maintenance}]' <<<"$addons")
  done < <(scalingo_lecture "$region" addons --app "$nom" | tableau_en_tsv | tail -n +2)

  conteneurs=$(scalingo_lecture "$region" ps --app "$nom" | tableau_en_tsv | tail -n +2 \
    | awk -F'\t' '{ sub(/-[0-9]+$/, "", $1); print $1 "\t" $4 "\t" $2 }' \
    | jq -R -s -c 'split("\n") | map(select(length > 0) | split("\t") | {type: .[0], taille: .[1], statut: .[2]})
        | group_by(.type, .taille) | map({type: .[0].type, taille: .[0].taille, nombre: length})')

  variables=$(scalingo_lecture "$region" env --app "$nom" | variables_de_version \
    | jq -R -s -c 'split("\n") | map(select(length > 0) | split("\t") | {(.[0]): .[1]}) | add // {}')

  depot=$(scalingo_lecture "$region" integration-link --app "$nom" | sed -nE 's/^Repository: *([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+).*/\1/p')

  deploiement=$(scalingo_lecture "$region" deployments --app "$nom" | tableau_en_tsv | tail -n +2 \
    | awk -F'\t' '$6=="success" && !vu {print $1 "\t" $2 "\t" $5; vu=1}')
  versions='{}'
  if [ -n "$deploiement" ]; then
    versions=$(scalingo_lecture "$region" deployment-logs --app "$nom" "${deploiement%%$'\t'*}" | versions_deployees \
      | jq -R -s -c 'split("\n") | map(select(length > 0) | split("\t")) | group_by(.[0]) | map({(.[0][0]): (map(.[1]) | join(" "))}) | add // {}')
  fi

  source_ligne=$(awk -F'\t' -v c="$composant" '$1==c{print $2 "\t" $3; exit}' <<<"$SOURCES")

  jq -n \
    --arg nom "$nom" --arg region "$region" --arg env "$env" --arg composant "$composant" \
    --arg projet "$projet" --arg statut "$statut" --arg stack "$stack" \
    --arg depotLie "$depot" --arg source "$source_ligne" --arg deploiement "$deploiement" \
    --argjson addons "$addons" --argjson conteneurs "$conteneurs" \
    --argjson variables "$variables" --argjson versions "$versions" \
    '{
      nom: $nom, region: $region, env: $env, composant: $composant, projet: $projet, statut: $statut, stack: $stack,
      source: (if $source == "" then null else ($source | split("\t") | {repo: .[0], dossier: .[1]}) end),
      depotLie: (if $depotLie == "" then null else $depotLie end),
      dernierDeploiement: (if $deploiement == "" then null else ($deploiement | split("\t") | {id: .[0], date: .[1], gitRef: .[2]}) end),
      versionsDeployees: $versions,
      variablesVersion: ($variables | with_entries(select(.key | startswith("#") | not))),
      buildpackUrlDefinie: ($variables["#BUILDPACK_URL"] != null),
      projectDirDefinie: ($variables["#PROJECT_DIR"] != null),
      addons: $addons,
      conteneurs: $conteneurs
    }' >"$TRAVAIL/apps/$nom.json"
  log "  $nom"
}

collecter_scalingo() {
  log "Scalingo"
  for region in "${REGIONS[@]}"; do
    scalingo_lecture "$region" stacks | tableau_en_tsv | tail -n +2 \
      | jq -R -s -c --arg region "$region" 'split("\n") | map(select(length > 0) | split("\t") | {region: $region, nom: .[1], description: .[2], parDefaut: (.[3] == "Yes")})' \
      >"$TRAVAIL/stacks-$region.json"
    while IFS=$'\t' read -r nom _role statut projet; do
      [ -n "${nom:-}" ] || continue
      collecter_app "$region" "$nom" "$statut" "$projet"
    done < <(scalingo_lecture "$region" apps | tableau_en_tsv | tail -n +2)
  done
}

normaliser() {
  sed -E 's/^[[:space:]"'"'"']+//; s/[[:space:]"'"'"',]+$//; s/^[~^>=<v ]+//'
}

brique_image() {
  local image=${1#docker.io/}
  image=${image#library/}
  case "$image" in
    postgres|postgis/postgis) echo postgresql ;;
    redis|redis/redis-stack) echo redis ;;
    node) echo node ;;
    quay.io/keycloak/keycloak) echo keycloak ;;
    hashicorp/terraform) echo terraform ;;
    eclipse-temurin) echo java ;;
    *) echo "image:$image" ;;
  esac
}

fait_image() {
  local fichier=$1 contexte=$2 reference=$3
  [[ "$reference" == *'$'* ]] && return 0
  local image=${reference%%:*} tag=latest
  [[ "$reference" == *:* ]] && tag=${reference#*:}
  local valeur
  valeur=$(sed -nE 's/^v?([0-9][0-9.]*).*/\1/p' <<<"$tag")
  printf '%s\t%s\t%s\t%s\t%s\n' "$fichier" "$contexte" "$(brique_image "$image")" "${valeur:-$tag}" "$reference"
}

fait() {
  local fichier=$1 contexte=$2 brique=$3 brut=$4
  local valeur
  valeur=$(normaliser <<<"$brut")
  [ -n "$valeur" ] || return 0
  printf '%s\t%s\t%s\t%s\t%s\n' "$fichier" "$contexte" "$brique" "$valeur" "$brut"
}

brique_de_variable() {
  case "$1" in
    JRE_MAJOR_VERSION|JAVA_VERSION) echo java ;;
    *) local b=${1%_VERSION}; b=${b,,}; echo "${b//_/-}" ;;
  esac
}

extraire_fichier() {
  local fichier=$1 contenu=$2 contexte
  case "$fichier" in
    .github/*) contexte=ci ;;
    */docker-compose*|docker-compose*|*/compose.*|compose.*|*Dockerfile*) contexte=local ;;
    *) contexte=depot ;;
  esac
  case "$fichier" in
    *.nvmrc|*.node-version) fait "$fichier" "$contexte" node "$(head -1 <<<"$contenu")" ;;
    *.python-version) fait "$fichier" "$contexte" python "$(head -1 <<<"$contenu")" ;;
    *runtime.txt) fait "$fichier" "$contexte" python "$(sed -nE 's/^python-//p' <<<"$contenu")" ;;
    *.fvmrc) fait "$fichier" "$contexte" flutter "$(jq -r '.flutter // .flutterSdkVersion // empty' <<<"$contenu")" ;;
    *package.json)
      fait "$fichier" "$contexte" node "$(jq -r '.engines.node // empty' <<<"$contenu")"
      fait "$fichier" "$contexte" yarn "$(jq -r '.engines.yarn // empty' <<<"$contenu")"
      fait "$fichier" "$contexte" yarn "$(jq -r '.packageManager // empty | select(startswith("yarn@")) | ltrimstr("yarn@") | split("+")[0]' <<<"$contenu")"
      ;;
    *.yarnrc.yml) fait "$fichier" "$contexte" yarn "$(sed -nE 's/^yarnPath:.*yarn-([0-9][0-9.]*)\.c?js.*/\1/p' <<<"$contenu")" ;;
    *system.properties) fait "$fichier" "$contexte" java "$(sed -nE 's/^java\.runtime\.version=(.*)/\1/p' <<<"$contenu")" ;;
    *gradle-wrapper.properties) fait "$fichier" "$contexte" gradle "$(sed -nE 's/.*gradle-([0-9][0-9.]*)-(bin|all)\.zip.*/\1/p' <<<"$contenu")" ;;
    *.buildpacks) fait "$fichier" "$contexte" buildpacks "$(sed -E '/^[[:space:]]*$/d' <<<"$contenu" | sed -E 's#^https://github\.com/##; s#\.git$##' | paste -sd ' ' -)" ;;
    *pubspec.yaml)
      fait "$fichier" "$contexte" dart "$(awk '/^environment:/{e=1; next} /^[^[:space:]#]/{e=0} e && $1=="sdk:"{print $2}' <<<"$contenu")"
      fait "$fichier" "$contexte" flutter "$(awk '/^environment:/{e=1; next} /^[^[:space:]#]/{e=0} e && $1=="flutter:"{print $2}' <<<"$contenu")"
      ;;
    *.tf)
      fait "$fichier" "$contexte" terraform "$(sed -nE 's/^[[:space:]]*required_version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' <<<"$contenu")"
      awk '
        /required_providers/ { p = 1 }
        p && /source[[:space:]]*=/ { gsub(/.*=[[:space:]]*"|".*/, ""); source = $0 }
        p && /version[[:space:]]*=/ && source != "" { gsub(/.*=[[:space:]]*"|".*/, ""); print source "\t" $0; source = "" }
      ' <<<"$contenu" | while IFS=$'\t' read -r provider version; do
        fait "$fichier" "$contexte" "provider:$provider" "$version"
      done
      ;;
    .github/variables/*)
      sed -nE 's/^([A-Z0-9_]+_VERSION)=(.*)/\1=\2/p' <<<"$contenu" | while IFS='=' read -r cle valeur; do
        fait "$fichier" "$contexte" "$(brique_de_variable "$cle")" "$valeur"
      done
      ;;
  esac
  case "$fichier" in
    *Dockerfile*)
      sed -nE 's/^[[:space:]]*FROM[[:space:]]+([^[:space:]]+).*/\1/Ip' <<<"$contenu" | while read -r ref; do
        fait_image "$fichier" "$contexte" "$ref"
      done
      sed -nE 's/^[[:space:]]*(ARG|ENV)[[:space:]]+([A-Z0-9_]+_VERSION)[[:space:]=]+"?([^"[:space:]]+)"?.*/\2\t\3/p' <<<"$contenu" \
        | while IFS=$'\t' read -r cle valeur; do fait "$fichier" "$contexte" "$(brique_de_variable "$cle")" "$valeur"; done
      ;;
    *.yml|*.yaml)
      sed -nE 's/^[[:space:]]*image:[[:space:]]*"?([^"[:space:]#]+)"?.*/\1/p' <<<"$contenu" | while read -r ref; do
        fait_image "$fichier" "$contexte" "$ref"
      done
      if [ "$contexte" = ci ]; then
        sed -nE 's/^[[:space:]]*(node|java|python|flutter|xcode|go|terraform)-version:[[:space:]]*(.+)$/\1\t\2/p' <<<"$contenu" \
          | sed '/\${{/d' | while IFS=$'\t' read -r brique valeur; do fait "$fichier" "$contexte" "$brique" "$valeur"; done
      fi
      ;;
  esac
}

composants_du_fichier() {
  local repo=$1 fichier=$2
  awk -F'\t' -v repo="$repo" -v f="$fichier" '
    $2 == repo && $3 != "-" {
      lg = ($3 == ".") ? 0 : length($3)
      if (lg == 0 || index(f, $3 "/") == 1) { if (lg > max) { max = lg; delete c; n = 0 } if (lg == max) c[++n] = $1 }
    }
    END { for (i = 1; i <= n; i++) print c[i] }
  ' max=-1 <<<"$SOURCES"
}

MOTIF_FICHIERS='(^|/)(\.nvmrc|\.node-version|\.python-version|runtime\.txt|\.fvmrc|package\.json|\.yarnrc\.yml|system\.properties|gradle-wrapper\.properties|\.buildpacks|pubspec\.yaml|[^/]*\.tf|Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|compose[^/]*\.ya?ml)$|^\.github/(workflows|actions)/.*\.ya?ml$|^\.github/variables/'

collecter_repos() {
  log "Repos"
  : >"$TRAVAIL/faits-repos.tsv"
  : >"$TRAVAIL/repos.tsv"
  for repo in "${REPOS[@]}"; do
    if [ "$repo" = pass-emploi-tools ]; then dossier=$TOOLS_ROOT; else dossier=$WORKSPACE/$repo; fi
    if [ ! -d "$dossier" ]; then log "  $repo : absent de $WORKSPACE, ignoré"; continue; fi
    if $FETCH; then git -C "$dossier" fetch --quiet origin 2>/dev/null || log "  $repo : fetch impossible, lecture des refs locales"; fi
    branche=$(git -C "$dossier" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
    printf '%s\t%s\t%s\t%s\n' "$repo" "$branche" "$(git -C "$dossier" rev-parse --short "$branche")" \
      "$(git -C "$dossier" log -1 --format=%cs "$branche")" >>"$TRAVAIL/repos.tsv"
    git -C "$dossier" ls-tree -r --name-only "$branche" | { grep -E "$MOTIF_FICHIERS" || true; } | sed '/node_modules/d' | while read -r fichier; do
      contenu=$(git -C "$dossier" show "$branche:$fichier")
      extraire_fichier "$fichier" "$contenu" | while IFS=$'\t' read -r f contexte brique valeur brut; do
        composants_du_fichier "$repo" "$f" | while read -r composant; do
          printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$composant" "$brique" "$contexte" "$valeur" "$repo" "$f" "$brut"
        done
      done
    done >>"$TRAVAIL/faits-repos.tsv"
    log "  $repo ($branche)"
  done
}

lire_version_cluster_elastic() {
  if [ -z "${ELASTIC_URL:-}" ] || [ -z "${ELASTIC_INVENTAIRE_API_KEY:-}" ]; then
    jq -n -c '{version: null, statut: "non lue (ELASTIC_URL ou ELASTIC_INVENTAIRE_API_KEY absente)"}'
    return
  fi
  local reponse
  if reponse=$(curl --silent --fail --max-time 20 \
      -H @<(printf 'Authorization: ApiKey %s\n' "$ELASTIC_INVENTAIRE_API_KEY") "${ELASTIC_URL%/}/" 2>/dev/null) \
    && jq -e '.version.number' <<<"$reponse" >/dev/null 2>&1; then
    jq -c '{version: .version.number, statut: "lue"}' <<<"$reponse"
  else
    printf '%s\t%s\t%s\n' elastic-cloud "GET /" "" >>"$TRAVAIL/erreurs.tsv"
    jq -n -c '{version: null, statut: "échec de GET / (URL, clé ou privilège monitor)"}'
  fi
}

assembler_inventaire() {
  jq -s -c '.' "$TRAVAIL"/apps/*.json >"$TRAVAIL/apps.json"
  jq -s -c 'add' "$TRAVAIL"/stacks-*.json >"$TRAVAIL/stacks.json"
  jq -R -s -c 'split("\n") | map(select(length > 0) | split("\t") | {repo: .[0], branche: .[1], commit: .[2], dateCommit: .[3]})' "$TRAVAIL/repos.tsv" >"$TRAVAIL/repos.json"
  jq -R -s -c 'split("\n") | map(select(length > 0) | split("\t")
    | {composant: .[0], brique: .[1], contexte: .[2], valeur: .[3], source: (.[4] + ":" + .[5]), brut: .[6]}) | unique' \
    "$TRAVAIL/faits-repos.tsv" >"$TRAVAIL/faits-repos.json"

  jq -R -s -c 'split("\n") | map(select(length > 0) | split("\t") | {region: .[0], commande: .[1], arguments: .[2]})' \
    "$TRAVAIL/erreurs.tsv" >"$TRAVAIL/erreurs.json"

  jq -n \
    --arg genereLe "$(date -Iseconds)" \
    --argjson regions "$(printf '%s\n' "${REGIONS[@]}" | jq -R -s -c 'split("\n") | map(select(length > 0))')" \
    --slurpfile apps "$TRAVAIL/apps.json" --slurpfile stacks "$TRAVAIL/stacks.json" \
    --slurpfile repos "$TRAVAIL/repos.json" --slurpfile faitsRepos "$TRAVAIL/faits-repos.json" \
    --slurpfile erreurs "$TRAVAIL/erreurs.json" --slurpfile elastic "$TRAVAIL/elastic.json" '
    def semver: split(".") | map(tonumber? // 0);
    def norm: ascii_downcase | sub("^v"; "");
    def compatibles($a; $b): ($a | norm) as $x | ($b | norm) as $y
      | $x != "latest" and $y != "latest"
        and ($x == $y or ($x | startswith($y + ".")) or ($y | startswith($x + ".")));
    def faits_scalingo: $apps[0][] as $app
      | ( {brique: "stack", valeur: $app.stack, source: "stack"} | select(.valeur != "")),
        ($app.versionsDeployees | to_entries[] | .key as $k | .value | split(" ")[] | {brique: (if $k == "buildpack" then "buildpack déployé" else $k end), valeur: ., source: "déployé"}),
        ($app.variablesVersion | to_entries[] | {brique: (.key | if . == "JRE_MAJOR_VERSION" or . == "JAVA_VERSION" then "java" else sub("_VERSION$"; "") | ascii_downcase | gsub("_"; "-") end), valeur: (.value | sub("^v"; "")), source: ("variable " + .key)}),
        ($app.addons[] | {brique: .type, valeur: (.version | sub("-[0-9]+$"; "")), source: ("addon " + .plan)})
      | . + {composant: $app.composant, contexte: $app.env, app: $app.nom};
    ([faits_scalingo] + $faitsRepos[0]) as $faits
    | ["prod", "staging", "perf", "depot", "ci", "local"] as $colonnes
    | ($faits | group_by(.composant, .brique) | map(
        . as $groupe
        | ([$groupe[].valeur] | unique) as $valeurs
        | {
            composant: $groupe[0].composant,
            brique: $groupe[0].brique,
            cellules: ($colonnes | map(. as $c | {key: $c, value: ([$groupe[] | select(.contexte == $c) | {valeur, source}] | unique)}) | from_entries),
            ecart: ([$valeurs[] as $a | $valeurs[] as $b | select(compatibles($a; $b) | not)] | length > 0)
          })) as $matrice
    | $elastic[0] as $cluster
    | ($faits | map(select(.brique == "logstash" or .brique == "elastic-agent" or .brique == "heartbeat")
        | . + {statut: (if $cluster.version == null then "inconnu"
            elif (.valeur | semver) > ($cluster.version | semver) then "violation"
            elif (.valeur | semver) == ($cluster.version | semver) then "aligné"
            else "en retard" end)})
        | sort_by((.statut != "violation"), (.statut != "en retard"), .app, .brique, .source)) as $stackElastic
    | {
        genereLe: $genereLe,
        regions: $regions,
        erreursCollecte: $erreurs[0],
        elasticCloud: $cluster,
        stackElastic: $stackElastic,
        repos: $repos[0],
        stacks: $stacks[0],
        apps: ($apps[0] | sort_by(.composant, .env)),
        faits: $faits,
        matrice: ($matrice | sort_by((.ecart | not), .composant, .brique))
      }' >"$TRAVAIL/inventaire.json"
}

ecrire_markdown() {
  jq -r '
    def cellule: if length == 0 then "" elif ([.[].valeur] | unique | length) == 1 then .[0].valeur
      else (group_by(.valeur) | map(.[0].valeur + " (" + (map(.source | split(":")[-1] | split(" ")[0]) | unique | join(", ")) + ")") | join(" / ")) end;
    def ligne: "| " + (map(tostring | gsub("\\|"; "\\|")) | join(" | ")) + " |";
    def tableau_matrice: (["Composant", "Brique", "prod", "staging", "perf", "dépôt", "CI", "local"] | ligne),
      "|---|---|---|---|---|---|---|---|",
      (.[] | [(if .ecart then "**" + .composant + "**" else .composant end), .brique,
        (.cellules.prod | cellule), (.cellules.staging | cellule), (.cellules.perf | cellule),
        (.cellules.depot | cellule), (.cellules.ci | cellule), (.cellules.local | cellule)] | ligne);
    "# Inventaire des versions Pass Emploi",
    "",
    "Généré le \(.genereLe) par `inventaire/inventaire-versions.sh`. Sortie datée : ne pas commiter.",
    "",
    "Sources : Scalingo (\(.regions | join(", "))) ; " + (.repos | map("\(.repo) `\(.branche)` \(.commit) (\(.dateCommit))") | join(", ")) + ".",
    "",
    (if (.erreursCollecte | length) > 0 then
      "**Collecte incomplète** : \(.erreursCollecte | length) appel(s) en échec, les cellules correspondantes sont vides à tort : " + (.erreursCollecte | map("`\(.commande) \(.arguments)` (\(.region))") | join(", ")) + ".", ""
    else empty end),
    "Colonnes : prod / staging / perf = Scalingo (version déployée au dernier déploiement réussi, variables `*_VERSION`, addons, stack) ; dépôt = fichiers lus au build Scalingo ; CI = `.github/` ; local = Dockerfiles et docker-compose.",
    "",
    "## Fins de vie (endoflife.date, au \(.finsDeVieCalculeesLe))",
    "",
    (.finsDeVie | map(select(.echeance != null))) as $aSignaler
    | (if ($aSignaler | length) > 0 then
        (["Échéance", "Composant", "Brique", "Produit endoflife.date", "Cycle", "Fin de vie", "Jours restants", "Où"] | ligne),
        "|---|---|---|---|---|---|---|---|",
        ($aSignaler[] | [(if .echeance == "dépassée" or .echeance == "< 30 j" then "**" + .echeance + "**" else .echeance end),
          .composant, .brique, .produit, .cycle, .eol, .joursRestants, .ouTexte] | ligne)
      else "Aucune fin de vie dépassée ni à moins de 6 mois." end),
    "",
    "\(.finsDeVie | map(select(.echeance == null)) | length) cycle(s) suivi(s) sans échéance à moins de 6 mois.",
    "",
    (if (.finsDeVieNonSuivies | length) > 0 then
      "Non suivi : " + (.finsDeVieNonSuivies | map("\(.brique) (\(.raison))") | join(", ")) + ".", ""
    else empty end),
    "## Stack Elastic : cluster \(.elasticCloud.version // .elasticCloud.statut)",
    "",
    "Invariant : aucune brique au-dessus de la version du cluster (violation). À chaque montée du cluster, aligner les briques en retard.",
    "",
    (if .elasticCloud.version == null then "Version du cluster \(.elasticCloud.statut) : comparaison impossible.", "" else empty end),
    (.stackElastic | map(select(.statut != "aligné"))) as $aSignaler
    | (if ($aSignaler | length) > 0 then
        (["Statut", "App", "Env", "Brique", "Version", "Source"] | ligne),
        "|---|---|---|---|---|---|",
        ($aSignaler[] | [(if .statut == "violation" then "**violation**" else .statut end), .app, .contexte, .brique, .valeur, .source] | ligne)
      else "Toutes les briques sont alignées sur le cluster." end),
    "",
    "\(.stackElastic | map(select(.statut == "aligné")) | length) ligne(s) alignée(s).",
    "",
    "## Écarts (\(.matrice | map(select(.ecart)) | length))",
    "",
    "Une ligne est en écart quand deux valeurs ne sont pas compatibles (l’une n’est pas un préfixe de l’autre), ou quand une valeur vaut `latest`.",
    "",
    (.matrice | map(select(.ecart)) | tableau_matrice),
    "",
    "## Matrice complète",
    "",
    (.matrice | tableau_matrice),
    "",
    "## Addons",
    "",
    (["App", "Env", "Type", "Plan", "Version", "Fenêtre de maintenance"] | ligne),
    "|---|---|---|---|---|---|",
    (.apps[] | . as $a | .addons[] | [$a.nom, $a.env, .type, .plan, .version, .maintenance] | ligne),
    "",
    "## Apps",
    "",
    (["App", "Région", "Env", "Statut", "Stack", "Conteneurs", "Dernier déploiement", "Dépôt lié", "Source (convention)", "BUILDPACK_URL"] | ligne),
    "|---|---|---|---|---|---|---|---|---|---|",
    (.apps[] | [.nom, .region, .env, .statut, .stack,
       (.conteneurs | map("\(.type) \(.nombre)×\(.taille)") | join(", ")),
       (if .dernierDeploiement then "\(.dernierDeploiement.date) `\(.dernierDeploiement.gitRef[0:7])`" else "aucun" end),
       (.depotLie // ""),
       (if .source then "\(.source.repo)/\(.source.dossier)" else "" end),
       (if .buildpackUrlDefinie then "définie" else "" end)] | ligne),
    "",
    "## Stacks disponibles",
    "",
    (["Région", "Stack", "Description", "Par défaut"] | ligne),
    "|---|---|---|---|",
    (.stacks[] | [.region, .nom, .description, (if .parDefaut then "oui" else "" end)] | ligne)
  ' "$SORTIE/inventaire.json" >"$SORTIE/inventaire.md"
}


# Scalingo installe Azul Zulu (buildpack jvm-common) ; la CI (setup-java) et les images, Temurin.
JQ_PRODUITS='
  def produit($brique; $contexte):
    if $brique == "java" then (if (["prod", "staging", "perf"] | index($contexte)) then "azul-zulu" else "eclipse-temurin" end)
    else {postgresql: "postgresql", redis: "redis", node: "nodejs", keycloak: "keycloak", python: "python",
      logstash: "logstash", heartbeat: "beats", yarn: "yarn", gradle: "gradle", terraform: "terraform",
      nginx: "nginx", metabase: "metabase", stack: "ubuntu", elasticsearch: "elasticsearch"}[$brique] end;
  def faits_suivis: .faits
    + (if .elasticCloud.version then [{composant: "elastic-cloud", brique: "elasticsearch", contexte: "prod", valeur: .elasticCloud.version, source: "cluster"}] else [] end)
    | map(. + {produit: produit(.brique; .contexte)});
'

calculer_fins_de_vie() {
  local entree=$1 produit fichier
  mkdir -p "$TRAVAIL/eol"
  : >"$TRAVAIL/erreurs-eol.tsv"
  jq -r "$JQ_PRODUITS"' faits_suivis | map(.produit // empty) | unique[]' "$entree" | while read -r produit; do
    fichier="$TRAVAIL/eol/$produit.json"
    if ! curl --silent --fail --max-time 20 -o "$fichier" "$EOL_API/$produit/" || ! jq -e '.result.releases' "$fichier" >/dev/null 2>&1; then
      rm -f "$fichier"
      printf '%s\t%s\t%s\n' endoflife.date GET "/api/v1/products/$produit/" >>"$TRAVAIL/erreurs-eol.tsv"
    fi
  done
  for fichier in "$TRAVAIL"/eol/*.json; do
    if [ -e "$fichier" ]; then jq -c --arg p "$(basename "$fichier" .json)" '{($p): .result.releases}' "$fichier"; fi
  done | jq -s -c 'add // {}' >"$TRAVAIL/eol.json"
  jq -R -s -c 'split("\n") | map(select(length > 0) | split("\t") | {region: .[0], commande: .[1], arguments: .[2]})' \
    "$TRAVAIL/erreurs-eol.tsv" >"$TRAVAIL/erreurs-eol.json"

  jq --slurpfile eol "$TRAVAIL/eol.json" --slurpfile erreursEol "$TRAVAIL/erreurs-eol.json" --arg aujourdhui "$(date +%F)" "$JQ_PRODUITS"'
    def semver: split(".") | map(tonumber? // 0);
    def version_produit: if .brique == "stack" then ((.valeur | capture("^scalingo-(?<n>[0-9]+)$").n + ".04") // .valeur) else .valeur end;
    def cycle($releases; $v):
      ([$releases[] | .name as $n | select($n == $v or ($v | startswith($n + ".")))] | sort_by(.name | length) | last)
      // ([$releases[] | select(.name | startswith($v + "."))] | sort_by(.name | semver) | last);
    def jours($date): (($date + "T00:00:00Z" | fromdateiso8601) - ($aujourdhui + "T00:00:00Z" | fromdateiso8601)) / 86400 | floor;
    def echeance: if . == null then null elif . <= 0 then "dépassée" elif . < 30 then "< 30 j" elif . < 183 then "< 6 mois" else null end;
    $eol[0] as $releases
    | faits_suivis as $faits
    | [$faits[] | select(.produit != null and $releases[.produit] != null) | . + {cycle: cycle($releases[.produit]; version_produit)}] as $rattaches
    | ($rattaches | map(select(.cycle != null)) | group_by(.composant, .brique, .produit, .cycle.name) | map(
        .[0].cycle.eolFrom as $date
        | (if $date then jours($date) else null end) as $j
        | {composant: .[0].composant, brique: .[0].brique, produit: .[0].produit, cycle: .[0].cycle.name,
           eol: $date, joursRestants: $j, echeance: ($j | echeance), derniereVersion: .[0].cycle.latest.name,
           versions: ([.[].valeur] | unique),
           ou: ([.[] | {contexte, valeur, source} + (if .app then {app} else {} end)] | unique),
           ouTexte: (sort_by(.contexte as $c | ["prod", "staging", "perf", "depot", "ci", "local"] | index($c))
             | map((if .contexte == "depot" then "dépôt" else .contexte end) + " " + .valeur)
             | reduce .[] as $o ([]; if any(.[]; . == $o) then . else . + [$o] end) | join(", "))})
      | sort_by((.joursRestants == null), .joursRestants, .composant, .brique)) as $finsDeVie
    | (([$faits[] | select(.produit == null) | .brique | select(. != "buildpacks" and . != "buildpack déployé")] | unique
        | map({brique: ., raison: "absent d’endoflife.date"}))
      + ([$faits[] | select(.produit != null and $releases[.produit] == null) | .produit] | unique
        | map({brique: ., raison: "endoflife.date injoignable"}))
      + ($rattaches | map(select(.cycle == null)) | group_by(.brique, .valeur)
        | map({brique: (.[0].brique + " " + .[0].valeur), raison: ("aucun cycle " + .[0].produit + " correspondant")})))
      as $nonSuivies
    | . + {finsDeVieCalculeesLe: $aujourdhui, finsDeVie: $finsDeVie, finsDeVieNonSuivies: $nonSuivies,
           erreursCollecte: ((.erreursCollecte | map(select(.region != "endoflife.date"))) + $erreursEol[0])}
  ' "$entree"
}

ecrire_corps_bulk() {
  jq -c '
    (now | floor) as $t
    | ($t | todate) as $horodatage
    | ("inventaire-versions-" + ($t | strftime("%Y%m%dT%H%M%SZ"))) as $run
    | .elasticCloud.version as $cluster
    | def sans_nuls: with_entries(select(.value != null) | .value |= tostring);
      def doc($kind; $action; $categorie; $id; $service; $message; $labels; $details):
        {"@timestamp": $horodatage,
         event: {provider: "inventaire-versions", kind: $kind, action: $action, id: ($run + "/" + ($id | gsub(" "; "_")))},
         service: $service,
         message: $message,
         labels: ({run_id: $run, categorie: $categorie} + $labels | sans_nuls)}
        + (if $details then {versions: $details} else {} end);
      def colonnes: [["prod", "prod"], ["staging", "staging"], ["perf", "perf"], ["depot", "dépôt"], ["ci", "ci"], ["local", "local"]];
      def code_echeance: {"dépassée": "depassee", "< 30 j": "moins_de_30_j", "< 6 mois": "moins_de_6_mois"}[.];
    (.matrice | map(select(.ecart))) as $ecarts
    | (.stackElastic | map(select(.statut == "violation"))) as $violations
    | (.stackElastic | map(select(.statut == "en retard"))) as $retards
    | (.finsDeVie | map(select(.echeance != null))) as $finsDeVie
    | [
        ($ecarts[] | . as $m
          | ([colonnes[] | . as [$cle, $libelle] | $m.cellules[$cle] | select(length > 0)
              | "\($libelle) \([.[].valeur] | unique | join("/"))"] | join(", ")) as $cellules
          | doc("event"; "version_mismatch_detected"; "ecart"; "ecart/\(.composant)/\(.brique)"; {name: .composant};
              "🔀 \(.composant) : \(.brique) en écart — \($cellules)"; {brique: .brique}; {cellules: .cellules})),
        ($violations[]
          | doc("alert"; "elastic_stack_version_ahead_detected"; "stack_elastic_violation"; "stack-elastic/\(.app)/\(.brique)/\(.source)";
              {name: .composant, environment: .contexte};
              "🚨 \(.app) : \(.brique) \(.valeur) au-dessus du cluster Elastic \($cluster) (\(.source))";
              {brique: .brique, version: .valeur, app: .app, source: .source, cluster_version: $cluster}; null)),
        ($retards[]
          | doc("event"; "elastic_stack_version_behind_detected"; "stack_elastic_retard"; "stack-elastic/\(.app)/\(.brique)/\(.source)";
              {name: .composant, environment: .contexte};
              "🐢 \(.app) : \(.brique) \(.valeur) en retard sur le cluster Elastic \($cluster) (\(.source))";
              {brique: .brique, version: .valeur, app: .app, source: .source, cluster_version: $cluster}; null)),
        ($finsDeVie[]
          | (.brique + " " + .cycle + (if .brique == "java" or .brique == "stack" then " (" + .produit + ")" else "" end)) as $quoi
          | (if .echeance == "dépassée" then "⛔ \(.composant) : \($quoi) en fin de vie depuis le \(.eol) — \(.ouTexte)"
             elif .echeance == "< 30 j" then "⏰ \(.composant) : \($quoi) en fin de vie le \(.eol), dans \(.joursRestants) j — \(.ouTexte)"
             else "⏳ \(.composant) : \($quoi) en fin de vie le \(.eol), dans \(.joursRestants) j — \(.ouTexte)" end) as $message
          | doc((if .echeance == "< 6 mois" then "event" else "alert" end); "end_of_life_detected"; "fin_de_vie";
              "fin-de-vie/\(.composant)/\(.produit)/\(.cycle)"; {name: .composant}; $message;
              {brique: .brique, produit: .produit, cycle: .cycle, eol: .eol, echeance: (.echeance | code_echeance), derniere_version: .derniereVersion};
              {jours_restants: .joursRestants, ou: .ou})),
        ({ecarts: ($ecarts | length), violations: ($violations | length), retards: ($retards | length),
          fins_de_vie_depassees: ($finsDeVie | map(select(.echeance == "dépassée")) | length),
          fins_de_vie_moins_de_30_j: ($finsDeVie | map(select(.echeance == "< 30 j")) | length),
          fins_de_vie_moins_de_6_mois: ($finsDeVie | map(select(.echeance == "< 6 mois")) | length),
          erreurs_collecte: (.erreursCollecte | length)} as $n
          | (.erreursCollecte | map("\(.commande) \(.arguments) (\(.region))" | sub(" +\\("; " ("))) as $erreurs
          | (if $n.erreurs_collecte > 0 or $cluster == null then "⚠️" else "📋" end) as $emoji
          | doc("event"; "inventory_completed"; "recapitulatif"; "recapitulatif"; {name: "inventaire-versions"};
              "\($emoji) Inventaire des versions : \($n.ecarts) écart(s), \($n.violations) violation(s) et \($n.retards) retard(s) de la stack Elastic, "
              + "\($finsDeVie | length) fin(s) de vie à moins de 6 mois dont \($n.fins_de_vie_depassees) dépassée(s), \($n.erreurs_collecte) erreur(s) de collecte"
              + (if $cluster == null then ", version du cluster Elastic non lue" else "" end)
              + (if $n.erreurs_collecte > 0 then " : " + ($erreurs[0:3] | join(", ")) + (if $n.erreurs_collecte > 3 then "…" else "" end) else "" end);
              {cluster_version: $cluster, inventaire_genere_le: .genereLe, erreurs_collecte: (if $n.erreurs_collecte > 0 then $erreurs | join(", ") else null end)};
              {compteurs: $n})
          | .event.outcome = (if $n.erreurs_collecte > 0 then "failure" else "success" end))
      ]
    | .[] | ({create: {}}, .)
  ' "$SORTIE/inventaire.json" >"$SORTIE/alertes-versions.ndjson"
}

envoyer_bulk() {
  local code
  code=$(curl --silent --show-error --max-time 60 -o "$TRAVAIL/bulk-reponse.json" -w '%{http_code}' -X POST \
      -H @<(printf 'Authorization: ApiKey %s\n' "$ELASTIC_ALERTES_VERSIONS_API_KEY") \
      -H 'Content-Type: application/x-ndjson' --data-binary @"$SORTIE/alertes-versions.ndjson" \
      "${ELASTIC_URL%/}/$DATA_STREAM/_bulk") || { log "Envoi impossible : Elasticsearch injoignable"; exit 1; }
  if [ "$code" != 200 ]; then
    log "Envoi refusé (HTTP $code) : $(jq -r '.error.type // "réponse illisible"' "$TRAVAIL/bulk-reponse.json" 2>/dev/null || echo 'réponse illisible')"
    exit 1
  fi
  jq -r '
    [.items[].create] as $items
    | ($items | map(select(.error))) as $refuses
    | ($items | map(select(.failure_store == "used"))) as $rejetes
    | "\($items | length - ($refuses | length) - ($rejetes | length)) document(s) indexé(s), \($refuses | length) refusé(s), \($rejetes | length) rejeté(s) par le pipeline (failure store, règle 14)",
      ($refuses[] | "  refusé : \(.error.type) : \(.error.reason)")
  ' "$TRAVAIL/bulk-reponse.json" >&2
  jq -e '[.items[].create | select(.error or .failure_store == "used")] | length == 0' "$TRAVAIL/bulk-reponse.json" >/dev/null
}

if [ -n "$DEPUIS" ]; then
  log "Inventaire repris de $DEPUIS"
  cp "$DEPUIS" "$TRAVAIL/inventaire.json"
else
  scalingo_lecture "${REGIONS[0]}" whoami | grep -q . || { log "CLI Scalingo non connectée : lancer 'scalingo login'"; exit 1; }
  collecter_scalingo
  collecter_repos
  log "Elastic Cloud"
  lire_version_cluster_elastic >"$TRAVAIL/elastic.json"
  assembler_inventaire
fi

log "Fins de vie (endoflife.date)"
calculer_fins_de_vie "$TRAVAIL/inventaire.json" >"$SORTIE/inventaire.json"
ecrire_markdown
log "Écrit : $SORTIE/inventaire.json et $SORTIE/inventaire.md"

if $SIMULER || $ENVOYER; then
  ecrire_corps_bulk
  log "Écrit : $SORTIE/alertes-versions.ndjson ($(($(wc -l <"$SORTIE/alertes-versions.ndjson") / 2)) document(s))"
fi
if $ENVOYER; then
  log "Envoi à $DATA_STREAM"
  envoyer_bulk
fi
