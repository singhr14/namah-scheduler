# Elasticsearch Autocomplete Update Summary

## Changes Made

### 1. Schema Update (`mongo_es_sync/config/constants.py`)

#### Added Autocomplete Analyzer Configuration
```python
"settings": {
    "analysis": {
        "analyzer": {
            "autocomplete_analyzer": {
                "tokenizer": "autocomplete_tokenizer",
                "filter": ["lowercase"]
            },
            "autocomplete_search_analyzer": {
                "tokenizer": "lowercase"
            }
        },
        "tokenizer": {
            "autocomplete_tokenizer": {
                "type": "edge_ngram",
                "min_gram": 2,
                "max_gram": 20,
                "token_chars": ["letter", "digit"]
            }
        }
    }
}
```

#### Updated Field Mappings

**Title Field** - Now supports partial word search:
```python
"title": {
    "type": "text",
    "analyzer": "autocomplete_analyzer",
    "search_analyzer": "autocomplete_search_analyzer",
    "fields": {
        "keyword": {"type": "keyword"}
    }
}
```

**Summary Field** - Now supports partial word search:
```python
"summary": {
    "type": "text",
    "analyzer": "autocomplete_analyzer",
    "search_analyzer": "autocomplete_search_analyzer"
}
```

**Tags Field** - Reverted to exact-match keyword:
```python
"tags": {"type": "keyword"}
```

### 2. Search Query Builder Update (`mongo_es_sync/core/search_query_builder.py`)

- **Removed** `tags` from `multi_match` search fields
- **Added** `tag` parameter for exact-match filtering
- **Updated** to search only `title` and `summary` with autocomplete
- All filter logic preserved (theme, deity, audience, language, tag)

## How It Works

### Autocomplete Behavior
- **Indexing**: Edge n-grams (2-20 chars) are created for title and summary
  - Example: "Krishna" → ["kr", "kri", "kris", "krish", "krishn", "krishna"]
- **Searching**: Uses lowercase tokenizer for search terms
  - Search "Kris" will match documents with "Krishna", "Krish", "Kristina", etc.

### Field Behavior Summary

| Field | Type | Search Type | Use Case |
|-------|------|-------------|----------|
| `title` | text (autocomplete) | Partial word match | Full-text autocomplete search |
| `summary` | text (autocomplete) | Partial word match | Full-text autocomplete search |
| `tags` | keyword | Exact match | Filter by exact tag value |
| `themes` | keyword | Exact match | Filter by exact theme value |
| `deities` | keyword | Exact match | Filter by exact deity value |
| `audiences` | keyword | Exact match | Filter by exact audience value |
| `language` | keyword | Exact match | Filter by exact language value |

## Example Queries

### 1. Autocomplete Search (Partial Word)
```python
query = build_search_query(search_text="Kris")
# Matches: "Krishna", "Krish", "Kristina" in title/summary
```

### 2. Exact Tag Filter
```python
query = build_search_query(tag="mythology")
# Only matches documents with exact tag "mythology"
```

### 3. Combined Search + Filters
```python
query = build_search_query(
    search_text="love dev",  # Autocomplete on title/summary
    theme="devotion",        # Exact match filter
    tag="spiritual",         # Exact match filter
    language="en"            # Exact match filter
)
```

### 4. Match All (No Filters)
```python
query = build_search_query(page=1, page_size=20)
# Returns all documents
```

## What Was NOT Changed

✅ MongoDB repository logic  
✅ Sync service logic  
✅ Scheduler configuration  
✅ Pagination logic  
✅ Business logic  
✅ Index name  
✅ Other field mappings  
✅ Document model structure  
✅ Indexing process flow  

## Migration Notes

**Important**: After deploying this change, you should:

1. **Delete and recreate the index** to apply the new analyzer settings:
   ```python
   # Delete existing index
   es_client.indices.delete(index="your_index_name")
   
   # The adapter will automatically recreate it with new settings
   ```

2. **Re-index all documents** to apply the new analyzers:
   ```python
   # Run full sync to re-index all documents
   python -m storysync.main --full-sync
   ```

**Note**: Analyzer settings cannot be updated on existing indices. The index must be recreated.

## Testing Autocomplete

Test the autocomplete functionality:

```python
# Test partial word matching
search_text = "Kris"  # Should match "Krishna"
search_text = "dev"   # Should match "devotion", "development"
search_text = "lov"   # Should match "love", "lovely"

# Minimum 2 characters required (min_gram = 2)
search_text = "K"     # Won't trigger autocomplete (too short)
search_text = "Kr"    # Will trigger autocomplete
```
