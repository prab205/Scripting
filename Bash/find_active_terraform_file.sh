find . -type f -name "terraform.tfstate" | while read -r file; do
    line_count=$(wc -l < "$file")
    if [ "$line_count" -gt 20 ]; then
        echo "File '$file' has more than 20 lines. The terraform file may be active"
    fi
done
