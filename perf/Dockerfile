FROM eclipse-temurin:24-jdk

COPY . /gatling
WORKDIR /gatling
RUN ./gradlew clean compileGatlingScala

ENTRYPOINT ["./entrypoint.sh"]
