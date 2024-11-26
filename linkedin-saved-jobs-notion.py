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

# Get the appropriate saved job URL
def get_saved_jobs_url(job_type='saved'):
	url_dict = {
		'saved': 'https://www.linkedin.com/my-items/saved-jobs/?cardType=SAVED',
		'applied': 'https://www.linkedin.com/my-items/saved-jobs/?cardType=APPLIED',
		'progress': 'https://www.linkedin.com/my-items/saved-jobs/?cardType=IN_PROGRESS',
		'archived': 'https://www.linkedin.com/my-items/saved-jobs/?cardType=ARCHIVED'
	}
	assert job_type.lower() in url_dict.keys(), 'not a recognized job type!'

	return url_dict[job_type.lower()]

# Collect the results on a page
# Args:
# - get_ext_link (bool): flag to get external application link
# - wait_time (float): how long to wait, in seconds, for dropdown menu to appear when getting external apply link (anecdotally should be >= 0.6)
# Returns: two lists of the same length
# - results: list of saved job content
# - apply_cont: list of dropdown elements (contains external application link)
def collect_results(get_ext_link=True, wait_time=0.6):
	html = browser.page_source
	soup = BeautifulSoup(html, 'html.parser')
	results = soup.find_all("div", attrs= {"class":"mb1"})
	assert len(results) > 0, "No results detected! (expected at least 1 saved job)"
	print("  Found " + str(len(results)) + " results")
	
	# only get external links if indicated, otherwise return a list of Nones
	if get_ext_link:
		# find all dropdowns
		dds = browser.find_elements(By.CLASS_NAME, "entity-result__actions-overflow-menu-dropdown")
		assert len(dds) > 0, "Expected to find dropdown elements in browser, but did not!"
		apply_cont = [get_apply_content_from_dropdown(dd, wait_time) for dd in dds]
	else:
		apply_cont = [None] * len(results)
	return results, apply_cont

# Parse the collected results
# Returns: list of lists, each containing job title, link to posting, external application link (or None), employer, location
def parse_results():
	inside_res = []
	any_apply_content = any(saved_ext)

	for res, apply_cont in zip(saved, saved_ext):
		# job title
		job = res.find("span", attrs = {"class":"t-16"})
		title = job.get_text().replace(', Verified', '').strip()
		link = job.find("a").get('href')
		li_link = re.split(r'[\\?]', link)[0]
		# company, location
		employer, location = [r.get_text().strip() for r in res.find_all("div", attrs = {"class":"t-14"})]

		ext_link = None
		# Only update the link if the text is 'Apply' (e.g., could be Easy Apply)
		if any_apply_content and apply_cont is not None:
			dd_apply = apply_cont.find("a")
			assert dd_apply is not None, "Expected to find a link in dropdown!"	
				
			if dd_apply.get_text().strip() == "Apply":
				ext_link = dd_apply.get("href")
			inside_res.append([title, li_link, ext_link, employer, location])
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

# Click and return the dropdown component for a saved job
# Args:
# - dd (WebElement): dropdown element for a saved job, detected by Selenium
# - wait_time (float): how long to wait, in seconds, for dropdown menu to appear when getting external apply link (anecdotally should be >= 0.6)
# Returns: the content of a the dropdown
def get_apply_content_from_dropdown(dd, wait_time=0.6):
    # click it to reveal the dropdown
    dd.click()
    time.sleep(wait_time) 
    # use bs4 to find the apply link/text
    dd_soup = BeautifulSoup(browser.page_source, "html.parser")
    dd_result = dd_soup.find("div", attrs={"class": "artdeco-dropdown__content-inner"})
    assert dd_result is not None, "expected to find a dropdown!"
	# need to "unclick"? TODO verify this
    dd.click()
    return dd_result

# Function to create an entry in a Notion database
def create_entry(title, url, url2, employer, location):
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


# What type of saved job?
# One of: 'saved', 'progress', 'applied', 'archived'
saved_job_type = 'saved'

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
browser.get(get_saved_jobs_url(saved_job_type))
login_to_linkedin()

# Iterate through each page and collect results 
# This is the only time we should be clicking through the browser
# Parsing will happen after
# Initiate the list of saved jobs and page counter
saved = []
saved_ext = []
next_page_exists = True
i = 1

# Override get_ext_link if job type is not saved
if saved_job_type.lower() != "saved":
    if retrieve_ext_links:
        print("job type is not 'saved', will not retrieve external links")
    retrieve_ext_links = False

# This could take a bit longer to run if you're getting the external links
# How much longer? approximately: number of saved jobs * wait_time (below)
while next_page_exists:
    print("Page " + str(i))
    time.sleep(2) # Turns out this is critical! Otherwise the page doesn't load properly and results won't populate
    results, apply_cont = collect_results(get_ext_link=retrieve_ext_links, wait_time=0.65)
    assert len(results) > 0, "No saved jobs detected! (expected at least 1)"
    saved.extend(results)
    saved_ext.extend(apply_cont)
    try:
        next_page_exists = next_page()
    except Exception:
        break
    i += 1

# Close browser
browser.close()

assert len(saved) > 0, "No results saved, expected more than one saved job!"
print("\nTotal collected jobs: " + str(len(saved)))

# Parse results
parsed_results = parse_results()
assert len(parsed_results) == len(saved), "Number of parsed results not equal to number saved!"
print("\nParsed results: " + str(len(parsed_results)))

# Copy new results into Notion database
notion = Client(auth=os.environ["NOTION_TOKEN"])

# Iterate through results, keeping track of how many consecutive existing entries there are 
# This way we can stop if we're just getting enough results that already exist
exist_count = 0
print("\nChecking for entries in Notion database\n")
for job in parsed_results:
    title, url, url2, employer, location = job
    print(title + " at " + employer)
    if exist_count >= exist_thresh:
        print("  Stopping because " + str(exist_thresh) + " consecutive entries already exist")
        break
    if not entry_exists(title, employer):
        exist_count = 0
        create_entry(title, url, url2, employer, location)
    else:
        exist_count += 1
        print("  Already exists")

# Print final message
print("\nDone!")
