# Mynotionarchive

Some automated scripts for my Notion archive.

## Paper archive autofill

`notion_paper_archive.py` looks for rows in a Notion database whose title has
been set manually and auto-fills the remaining metadata with Semantic Scholar
results.

### Setup

1. Create a Notion integration at <https://www.notion.so/my-integrations>, copy
   its **Internal Integration Secret** as your notion token.
2. Grab the database ID from **link**. The 32-character string at
   the end of the URL is the value you need for `NOTION_DATABASE_ID`.
3. Install the dependencies: `pip install -r requirements.txt`.

### Run

```bash
python notion_paper_archive.py \
  --notion-token "Your notion token"\
  --database-id "Your notion database id" \
```

Add `--dry-run` to preview updates without writing to Notion.