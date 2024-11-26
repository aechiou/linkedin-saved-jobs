# Scrape LinkedIn saved jobs

Python scripts to export information about saved jobs on LinkedIn to either: 
1. CSV file, or
2. Notion database

In either case, your LinkedIn credentials should be stored as environmental variables:
-  `LI_USER`: Your LinkedIn username
-  `LI_PASS`: Your LinkedIn password

## 1. CSV version

This version creates a CSV file containing a row for each saved job, and the following columns:
- `title`: Job title
- `url`: URL for LinkedIn posting
- `url2`: (Optional) URL for corresponding external application link
- `employer`: Employer
- `location`: Location

## 2. Notion integration version

This version updates an existing Notion database to add newly saved jobs, containing the following properties:
- `Name`: Job title
- `Status`: Status (one of which must be "Not started")
- `URL`: URL for LinkedIn posting
- `URL 2`: URL for corresponding external application link
- `Company`: Employer
- `Location`: Location

- Additional environmental variables are required for this version:
    - `NOTION_TOKEN`: Your Notion API token ([how to create one](https://developers.notion.com/reference/create-a-token))
    - `NOTION_DATABASE_ID`: The database ID ([how to find this](https://developers.notion.com/reference/retrieve-a-database))

## Dependencies
Developed using: Python 3.9.12, `selenium 4.24.0`, `beautifulsoup4 4.11.1`, `pandas 2.2.2`, and `notion-client 2.2.1`