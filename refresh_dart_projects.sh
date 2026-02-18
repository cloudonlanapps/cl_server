#!/usr/bin/env bash

CURRENT_DIR=$(pwd)

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --clean    Perform only flutter clean for every project in $CURRENT_DIR"
    echo "  -h, --help Show this help message"
    echo ""
    echo "Refresh all flutter projects in $CURRENT_DIR"
    exit 0
fi

CLEAN_ONLY=false
if [ "$1" = "--clean" ]; then
    CLEAN_ONLY=true
fi

find "$CURRENT_DIR" -name pubspec.yaml -type f | while read -r pubspec; do
    dir=$(dirname "$pubspec")
    echo "$dir is a flutter project"
    pushd "$dir" || exit
    flutter clean
    if [ "$CLEAN_ONLY" = false ]; then
        flutter pub get
    fi
    popd || exit
done
