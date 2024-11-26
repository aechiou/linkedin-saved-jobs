Python script to export information about saved jobs on LinkedIn to CSV file.

The CSV file will contain, for each saved job:
- Job title
- URL for LinkedIn posting
- (Optional) URL for corresponding external application link
- Employer
- Location

The following environmental variables are required:
-  `LI_USER`: Your LinkedIn username
-  `LI_PASS`: Your LinkedIn password
- If using Notion database integration:
    - `NOTION_TOKEN`: Your Notion API token ([how to create one](https://developers.notion.com/reference/create-a-token))
    - `NOTION_DATABASE_ID`: The database ID ([how to find this](https://developers.notion.com/reference/retrieve-a-database))

Developed using: Python 3.9.12, `selenium 4.24.0`, `beautifulsoup4 4.11.1`, `pandas 2.2.2`, and `notion-client 2.2.1`