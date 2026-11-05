# Clean-machine check: JDK 17 + Maven 3.9.9 + Python, as in scripts/install_env.sh.
#   docker build -f src/testdebt/team/gulsher/Dockerfile -t verirefactor .
#   docker run --rm -it --env-file .env verirefactor bash scripts/setup_projects.sh
FROM eclipse-temurin:17-jdk-jammy
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip python3-venv git curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -sSfL https://archive.apache.org/dist/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz \
    | tar -xz -C /opt && ln -s /opt/apache-maven-3.9.9/bin/mvn /usr/local/bin/mvn
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip3 install --no-cache-dir -r requirements.txt && pip3 install --no-cache-dir -e .
COPY . .
RUN bash src/testdebt/team/hasan/get_jnose.sh
CMD ["python3", "-m", "pytest", "-q"]
