FROM eclipse-temurin:21-jdk

COPY . /gatling
WORKDIR /gatling
RUN ./gradlew clean compileGatlingScala

ENTRYPOINT ["./entrypoint.sh"]
