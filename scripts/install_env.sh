#!/usr/bin/env bash
# One-time WSL/Ubuntu setup: JDK 17 (the pinned Gson/Jsoup builds refuse JDK 18+ / need -source 1.7 support),
# Maven 3.9.9 (Apache projects reject Maven < 3.9), Python venv.
set -euo pipefail
sudo apt-get update -y
sudo apt-get install -y openjdk-17-jdk git python3-venv wget
if ! mvn -v 2>/dev/null | grep -q "Apache Maven 3\.9"; then
  cd "$HOME"
  [ -d apache-maven-3.9.9 ] || { wget -q https://archive.apache.org/dist/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz && tar xzf apache-maven-3.9.9-bin.tar.gz; }
  for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    [ -f "$rc" ] && ! grep -q apache-maven-3.9.9 "$rc" && echo 'export PATH=$HOME/apache-maven-3.9.9/bin:$PATH' >> "$rc"
  done
  echo "Maven 3.9.9 installed. Run:  export PATH=\$HOME/apache-maven-3.9.9/bin:\$PATH   (or open a new shell)"
fi
ls -d /usr/lib/jvm/java-17-openjdk-* && echo "JDK 17 OK"
