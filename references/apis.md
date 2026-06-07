# Verification APIs

All free, no key. Send a descriptive User-Agent (polite pool).

## Crossref (primary, DOIs)
GET https://api.crossref.org/works?query.bibliographic=<ref>&rows=5
Fields used: message.items[0].DOI, .title[0], .author[].family, .issued.date-parts[0][0]

## arXiv (preprints, no DOI)
GET http://export.arxiv.org/api/query?search_query=ti:<title>&max_results=5
Atom XML. Fields: entry/title, entry/id (-> 1234.56789), entry/author/name, entry/published

## OpenAlex (catch-all)
GET https://api.openalex.org/works?search=<ref>&per-page=5
Fields: results[0].display_name, .publication_year, .doi, .ids.openalex, .authorships[].author.display_name

## Rate-limit etiquette
Polite-pool User-Agent; exponential backoff on 429/503; cap retries then report NOT_FOUND
(reason: ratelimit). Never guess a pass on a network error.
