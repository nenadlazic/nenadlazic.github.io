#!/bin/bash

# Build hugo
hugo

if [ $? -ne 0 ]; then
  echo "Hugo build failed!"
  exit 1
fi

rm -rf docs/*

cp -r public/* docs/

echo "Successfully completed."

