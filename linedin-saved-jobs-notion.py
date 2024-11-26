# %%
# ---- Imports ----
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

import os
import time
import re
from notion_client import Client

# %%
# ---- Functions ----
# Log into LinkedIn
# Requires LI_USER and LI_PASS env vars
# Args:
# - wait_to_verify (bool): Flag to add wait time at end of function (allows time for 2 step verification)
def login_to_linkedin(wait_to_verify=False):
	wait = WebDriverWait(browser, 30)
	wait.until(EC.element_to_be_clickable((By.ID, "username"))).send_keys(os.environ['LI_USER'])
	wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys(os.environ['LI_PASS'])
	wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))).click()
	print("Logged in")
	if wait_to_verify:
		time.sleep(60)

# Collect the results on a page
def collect_results():
	html = browser.page_source
	soup = BeautifulSoup(html, 'html.parser')
	results = soup.find_all("div", attrs= {"class":"mb1"})
	assert len(results) > 0, "No results detected! (expected at least 1 saved job)"
	print("  Found " + str(len(results)) + " results")
	return results

# Parse the collected results
# Extracts job title, link to posting, employer, location
# Args:
# - get_ext_link (bool): Flag to get external link
# Returns: list of lists
def parse_results(get_ext_link=True):
	inside_res = []
	for res in saved:
		# job title
		job = res.find("span", attrs = {"class":"t-16"})
		title = job.get_text().replace(', Verified', '').strip()
		link = job.find("a").get('href')
		li_link = re.split(r'[\\?]', link)[0]
		ext_link = None
		if get_ext_link:
			ext_link = get_apply_link(li_link)
		# company, location
		employer, location = [r.get_text().strip() for r in res.find_all("div", attrs = {"class":"t-14"})]

		if get_ext_link:
			inside_res.append([title, li_link, ext_link, employer, location])
		else:
			inside_res.append([title, li_link, employer, location])
	return inside_res

# Determines whether there is a next page
# Returns: bool
def next_page():
	time.sleep(1)
	test = browser.find_element(By.XPATH, "//button[@aria-label='Next']")
	if test.is_enabled():
		try:
			test.click()
			return True
		except Exception as e:
			return False
	else:
		print('No more pages')
		return False

# Function to get the external job application link
# Works by navigating the browser to the LinkedIn page, then clicking Apply
def get_apply_link(link):
	browser.get(link)
	time.sleep(1)
	test = browser.find_element(By.CLASS_NAME, "jobs-apply-button--top-card")
	if test.is_enabled() and test.text == "Apply":
		try: 
			test.click()
			browser.switch_to.window(browser.window_handles[1])
			url = browser.current_url
			browser.close()
			browser.switch_to.window(browser.window_handles[0])
			return url
		except Exception as e:
			browser.back()
			print(f"Error getting apply link: {e}")
			return None
	else:
		return None

# Function to create an entry in a Notion database
def create_entry(title, url, url2, employer, location, get_ext_link=True):
    # Overwrite url2 if getting external link
    if get_ext_link:
        url2 = get_apply_link(url)
    new_page = {
        "Name": {
            "title": [{"text": {"content": title}}]
        },
        "Status": {
            "type": "status",
            "status": {"name": "Not started"}
        },
        "Company": {
            "type": "rich_text",
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": employer},
                },
            ],
        },
        "URL": {
            "type": "url",
            "url": url
        },
        "URL 2": {
            "type": "url",
            "url": url2
        },
        "Location": {
            "type": "rich_text",
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": location},
                },
            ],
        },
    }
    notion.pages.create(parent={"database_id": os.environ['NOTION_DATABASE_ID']}, properties=new_page)
    print("  Added to DB")

# Function to check if an entry in a Notion database
# Only checks for matching job title and employer
def entry_exists(title, company):
    results = notion.databases.query(
        database_id=os.environ['NOTION_DATABASE_ID'],
        filter={
            "and": [
                {
                    "property": "Name",
                    "rich_text": {
                        "equals": title
                    }
                }, 
                {
                    "property": "Company",
                    "rich_text": {
                        "equals": company
                    }
                }
            ]
        }
    ).get("results")
    return len(results) > 0

# %%
# ---- Params ----

# URL for saved jobs
# Can use cardType=APPLIED to get jobs applied to via LinkedIn
saved_jobs_url = 'https://www.linkedin.com/my-items/saved-jobs/?cardType=SAVED'

# Whether to retrieve external application links
retrieve_ext_links = True

# How many consecutive entries should already exist in the Notion database before we stop checking?
# Set to a very high number if you want to add all new and don't mind waiting
exist_thresh = 10

# %%
# ---- Run script ----

# Open a Chrome browser to LinkedIn saved jobs, then log in
# Requires LI_USER and LI_PASS environment variables
browser = webdriver.Chrome()
browser.get(saved_jobs_url)

login_to_linkedin()

# Iterate through each page and collect results (parsing will happen after)
# Initiate the list of saved jobs and page counter
saved = []
next_page_exists = True
i = 1
while next_page_exists:
    print("Page " + str(i))
    time.sleep(2) # Turns out this is critical! Otherwise the page doesn't load properly and results won't populate
    results = collect_results()
    saved.extend(results)
    try:
        next_page_exists = next_page()
    except Exception:
        break
    i += 1

assert len(saved) > 0, "No results saved, expected more than one saved job!"
print("\nTotal collected jobs: " + str(len(saved)))

# We don't get the external links for the Notion integration!
# Only will fetch them if the entry doesn't exist in the database yet
parsed_results = parse_results(get_ext_link=False)

assert len(parsed_results) == len(saved), "Number of parsed results not equal to number saved!"
print("\nParsed results: " + str(len(parsed_results)))

# Copy new results into Notion database
notion = Client(auth=os.environ["NOTION_TOKEN"])

# Iterate through results, keeping track of how many consecutive existing entries there are 
# This way we can stop if we're just getting enough results that already exist
exist_count = 0
for job in parsed_results:
    title, url, url2, employer, location = job
    print(title + " at " + employer)
    if exist_count >= exist_thresh:
        print("  Stopping because " + str(exist_thresh) + " consecutive entries already exist")
        break
    if not entry_exists(title, employer):
        exist_count = 0
        create_entry(title, url, url2, employer, location, get_ext_link=retrieve_ext_links)
    else:
        exist_count += 1
        print("  Already exists")

# Close browser and print final message
browser.close()
print("Done")
