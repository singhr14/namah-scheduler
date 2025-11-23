"""
Search query builder for Elasticsearch with filtering support.
Provides methods to build search queries with full-text search and filters.
"""
from typing import Dict, Any, Optional, List


def build_search_query(
    search_text: Optional[str] = None,
    theme: Optional[str] = None,
    deity: Optional[str] = None,
    audience: Optional[str] = None,
    language: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> Dict[str, Any]:
    """
    Build Elasticsearch search query with full-text search and filters.
    
    Args:
        search_text: Text to search across title and summary with autocomplete (optional)
        theme: Filter by theme (exact match, optional)
        deity: Filter by deity (exact match, optional)
        audience: Filter by audience (exact match, optional)
        language: Filter by language (exact match, optional)
        tag: Filter by tag (exact match, optional)
        page: Page number (1-indexed)
        page_size: Number of results per page
        
    Returns:
        Dict[str, Any]: Elasticsearch query body
    """
    query_body: Dict[str, Any] = {
        "from": (page - 1) * page_size,
        "size": page_size
    }
    
    # Build the query clause
    must_clauses = []
    
    # Full-text autocomplete search across title and summary only
    if search_text and search_text.strip():
        must_clauses.append({
            "multi_match": {
                "query": search_text,
                "fields": [
                    "title", "title.as_you_type",
                    "summary", "summary.as_you_type",
                    "tags", "tags.as_you_type",
                    "deities", "deities.as_you_type"
                ],
                "type": "best_fields",
                "operator": "or"
            }
        })
    
    # Build filter clauses for exact matches
    filter_clauses = []
    
    if theme and theme.strip():
        filter_clauses.append({"term": {"themes": theme}})
    
    if deity and deity.strip():
        filter_clauses.append({"term": {"deities": deity}})
    
    if audience and audience.strip():
        filter_clauses.append({"term": {"audiences": audience}})
    
    if language and language.strip():
        filter_clauses.append({"term": {"language": language}})
    
    if tag and tag.strip():
        filter_clauses.append({"term": {"tags": tag}})
    
    # Construct the bool query
    if must_clauses or filter_clauses:
        bool_query = {"bool": {}}
        
        if must_clauses:
            bool_query["bool"]["must"] = must_clauses
        
        if filter_clauses:
            bool_query["bool"]["filter"] = filter_clauses
        
        query_body["query"] = bool_query
    else:
        # No search text and no filters - return all documents
        query_body["query"] = {"match_all": {}}
    
    return query_body


def build_search_query_with_sorting(
    search_text: Optional[str] = None,
    theme: Optional[str] = None,
    deity: Optional[str] = None,
    audience: Optional[str] = None,
    language: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "updated_at",
    sort_order: str = "desc"
) -> Dict[str, Any]:
    """
    Build Elasticsearch search query with sorting support.
    
    Args:
        search_text: Text to search across title and summary with autocomplete (optional)
        theme: Filter by theme (exact match, optional)
        deity: Filter by deity (exact match, optional)
        audience: Filter by audience (exact match, optional)
        language: Filter by language (exact match, optional)
        tag: Filter by tag (exact match, optional)
        page: Page number (1-indexed)
        page_size: Number of results per page
        sort_by: Field to sort by
        sort_order: Sort order ('asc' or 'desc')
        
    Returns:
        Dict[str, Any]: Elasticsearch query body with sorting
    """
    query_body = build_search_query(
        search_text=search_text,
        theme=theme,
        deity=deity,
        audience=audience,
        language=language,
        tag=tag,
        page=page,
        page_size=page_size
    )
    
    # Add sorting
    query_body["sort"] = [{sort_by: {"order": sort_order}}]
    
    return query_body


# Example usage
if __name__ == "__main__":
    import json
    
    # Example 1: Autocomplete search with partial text (title/summary only)
    query1 = build_search_query(search_text="Kris")
    print("Example 1 - Autocomplete text search (partial word):")
    print(json.dumps(query1, indent=2))
    print()
    
    # Example 2: Search with filters only (including tag exact match)
    query2 = build_search_query(theme="devotion", deity="Krishna", language="en", tag="mythology")
    print("Example 2 - Filters only (including exact tag match):")
    print(json.dumps(query2, indent=2))
    print()
    
    # Example 3: Autocomplete search with text and filters
    query3 = build_search_query(
        search_text="love dev",
        theme="devotion",
        audience="children",
        language="en",
        tag="spiritual"
    )
    print("Example 3 - Autocomplete text search with filters:")
    print(json.dumps(query3, indent=2))
    print()
    
    # Example 4: Match all (no search text, no filters)
    query4 = build_search_query(page=1, page_size=20)
    print("Example 4 - Match all:")
    print(json.dumps(query4, indent=2))
    print()
    
    # Example 5: With sorting
    query5 = build_search_query_with_sorting(
        search_text="Kris",
        theme="devotion",
        tag="mythology",
        sort_by="created_at",
        sort_order="desc"
    )
    print("Example 5 - Autocomplete with sorting:")
    print(json.dumps(query5, indent=2))
