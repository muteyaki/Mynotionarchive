# Mynotionarchive

Some automated scripts for my Notion archive.

## Paper archive autofill

`notion_paper_archive.py` looks for rows in a Notion database whose title has
been set manually and automatically fills in the remaining metadata by querying
Semantic Scholar.

### Prerequisites

1. Create a Notion internal integration and share your paper database with it.
2. Install the Python dependencies

   ```bash
   pip install -r requirements.txt
   ```
3. Export the following environment variables (or pass them as CLI arguments):

   - `NOTION_TOKEN`: the integration token generated in step 1.
   - `NOTION_DATABASE_ID`: the ID of the database that should be updated.
   - Optional overrides for property names: `NOTION_TITLE_PROPERTY`,
     `NOTION_AUTHORS_PROPERTY`, `NOTION_DATE_PROPERTY`,
     `NOTION_VENUE_PROPERTY`, `NOTION_CITATION_PROPERTY`,
     `NOTION_ABSTRACT_PROPERTY`.

   To get the database ID, open the database as a full page in Notion, copy
   the **Share** → **Copy link** URL, and grab the 32-character string between
   the last `/` and the `?` query parameters (or after `/` if no query string).
   For example, in a link like
   `https://www.notion.so/workspace/My-Papers-1234567890abcdef1234567890abcdef?pvs=4`,
   the database ID is `1234567890abcdef1234567890abcdef`.

The target database should have a title property (default: `Name`) and text (or
multi-select for authors) properties for the metadata you want to auto-fill.

### Usage

Run the script whenever you add new titles to the database:

```bash
python notion_paper_archive.py \
  --database-id "$NOTION_DATABASE_ID" \
  --authors-property "Authors" \
  --date-property "Published" \
  --venue-property "Venue" \
  --citation-property "Citation" \
  --abstract-property "Abstract"
```

Add `--dry-run` to preview the updates without patching the database.  By
default the script pulls publication data from Semantic Scholar, derives a
simple citation string, and writes them back to Notion.
