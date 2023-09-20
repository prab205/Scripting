#!/bin/bash

# if no any values passed, then current directory
if [ -z "$1" ]; then
  directory="."
else
  directory="$1"
fi


file_list=($(ls -lt $directory | awk '{print $NF}'))

# Remove the first item (total size by the directory)
file_list=("${file_list[@]:1}")

# Loop through the remaining items and print disk usage
for item in "${file_list[@]}"; do
  sudo du -sh "$directory/$item"
done

