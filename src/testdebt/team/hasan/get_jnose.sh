#!/usr/bin/env bash
# Download JNose (jnose-core 0.9.0, the last release compiled for Java 21; 0.9.3 needs Java 25) and its parser.
set -euo pipefail
cd "$(dirname "$0")/../../../.."
D=data/tools/jnose
mkdir -p "$D"
M=https://repo1.maven.org/maven2
curl -sSfo "$D/jnose-core-0.9.0.jar" "$M/io/github/arieslab/jnose-core/0.9.0/jnose-core-0.9.0.jar"
curl -sSfo "$D/javaparser-core-3.3.5.jar" "$M/com/github/javaparser/javaparser-core/3.3.5/javaparser-core-3.3.5.jar"
echo "JNose jars in $D (the wrapper compiles itself on first use)"
