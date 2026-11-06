FROM eclipse-temurin:25-jdk

COPY . /gatling
WORKDIR /gatling
RUN ./gradlew clean compileGatlingScala

ENTRYPOINT ["./entrypoint.sh"]
