import json
import logging
import os
import sys, time
import requests
from datetime import datetime
from urllib.request import Request, urlopen
from time import strptime
from bs4 import BeautifulSoup
from cryptography.fernet import Fernet
import warnings
from jira.client import JIRA

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger('verify-rit-test-plan')
verification_result = {
    "rule_name": "verify-rit-test-execution",
    "description": "This Docker image verifies the Verify Test Scope page Exists, "
                   "Verify in Functional Section that ID column is not empty"
                   "Verify ID link exists in Test Scope for each module",
    "rule_version": "",
    "message": "",
    "verified": False,
    "version": 3,
    "link_to_more_info": "https://github.theocc.com/good-software-delivery-org/verify-rit-test-execution/blob/master/"
                         "master/README.md#additional-information",
    "compliance": {
        "type": "COBIT2019",
        "control_id": "BAI02_ETD_002",
        "activity_id": "BAI02.01.01, BAI02.01.02, BAI02.01.03,BAI02.01.01"}
}

def decrypt_token():
    """decrypt jenkins_jira service account token"""
    token = open("C:\\Users\\SMAKA01\\ORGREPO\\verify-jira-traceability\\certificates\\token", "rb").read()
    key = Fernet(token)
    jira_token = key.decrypt(b'gAAAAABg9c0pXpKO2PAqxwdeZM5vdnPwa51wu53wsVeZZSNjzYAJitbrBlBMPKtDEwxdiQcgi9G0vmrVElX3Pmu'
                             b'5rhDBB7tPjxD3gsm5VxfcVJfZpadwv8k=')
    return jira_token

def set_rule_version():
    """Define the variable RULE_VERSION """
    if not os.getenv("RULE_VERSION"):
        logger.error("Rule version not set")
        verification_result["rule_version"] = "NONE"
    else:
        verification_result["rule_version"] = os.environ["RULE_VERSION"]





def get_from_environment(variable_name):
    """Returns a given environment variable"""
    failure_message = f"[FAIL] {variable_name} not available in environment, or is empty"
    try:
        value = os.environ[variable_name]
        if not value:
            logger.error(failure_message)
            sys.exit(1)
        return value
    except KeyError:
        logger.error(failure_message)
        sys.exit(1)


def table_search(confluence_api_data, table_name, unique_section_in_table):
    """Find a specific table in provided html data"""
    main_body = confluence_api_data.find('div', {'id': 'main-content'})
    table_collection = main_body.find_all('div', class_='table-wrap')
    logger.info(f"number of total tables on confluence page:  {len(table_collection)}")
    header_count = 0
    wanted_table = []
    for table in table_collection:
        for table_header in table.find_all('tr'):
            if unique_section_in_table in table_header.text:
                header_count += 1
        if header_count == 1:
            wanted_table.append(table)
            logger.info(f"found {table_name} table:  {table}")
        header_count = 0
    if len(wanted_table) != 1:
        error_message = f"[FAIL] Could not locate {table_name} table for the Confluence page.\n"
        logger.error(error_message)
        verification_result['verified'] = False
        verification_result['message'] += error_message
        return None

    return wanted_table[0]


def parseZephyrtestcases(issue_id_link):
    """Find all Zephyr test cases in test executions"""
    ISSUE_ID = str(issue_id_link).split('/')[-1]
    url = JIRA_API_URL + ZEPHYR_API_URL + str(ISSUE_ID)
    logger.info("url is " + url)
    jiraNum = ISSUE_ID
    try:
        proxies = {
            "http": f"http://{PROXY_USR}:{PROXY_PSW}@{PROXY_HOST}:{PROXY_PORT}",
            "https": f"http://{PROXY_USR}:{PROXY_PSW}@{PROXY_HOST}:{PROXY_PORT}"
        }
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = requests.get(url, auth=(JIRA_USER, decrypt_token()), proxies=proxies, verify=False)
            res_json = response.json()

        issue_links = res_json['executions']
        for issue in issue_links:
            executedOn = issue['executedOn']
            try:
                split_date = executedOn.split("/")
                date_format = datetime.strptime(
                    '20' + split_date[2] + '-' + str(strptime(split_date[1], "%b").tm_mon) + "-" + split_date[0],
                    "%Y-%m-%d")
            except:
                date_format = None
                executedOn = None

            if executedOn in ["", None]:
                error_message = f"[FAIL] Zephyr Test cases are not executed in {jiraNum}.\n"
                logger.error(error_message)
                verification_result['verified'] = False
                verification_result['message'] += error_message
                return verification_result
            elif date_format < datetime.now():
                continue
            else:
                error_message = f"[FAIL] Zephyr Test cases are not executed in {jiraNum}.\n"
                logger.error(error_message)
                verification_result['verified'] = False
                verification_result['message'] += error_message
                return verification_result

        message = f"[Pass] Zephyr Test cases are Executed in {jiraNum}.\n"
        logger.info(message)
        verification_result['verified'] = True
        verification_result['message'] += message
        return verification_result

    except Exception as e:
        error_message = f"[FAIL] Zephyr Test cases are not executed in {jiraNum}.\n" + str(sys.exc_info())
        logger.error(error_message)
        verification_result['verified'] = False
        verification_result['message'] += error_message
        return verification_result


def parseJiraStory(jiraStoryContent, link):
    """Find all the jira stories in testedby section """
    global testStories
    jiraNum = link.split("/")[-1]
    foundTestedBy = False
    soup = BeautifulSoup(jiraStoryContent, 'html.parser')
    list_collection = soup.find_all('dl')
    for item in list_collection:
        if item.find_all('dt', title='tested by'):
            jiraCollection = item.find_all('a', class_='issue-link link-title resolution')
            if not jiraCollection:
                jiraCollection = item.find_all('a', class_='issue-link link-title')
            for link in jiraCollection:
                foundTestedBy = True
                testStories.append("https://pappa30l:8443" + link.get('href'))

    if not foundTestedBy:
        error_message = f"[FAIL] Tested by section is not present in the jira {jiraNum}.\n"
        logger.error(error_message)
        verification_result['verified'] = False
        verification_result['message'] += error_message
        return verification_result
    else:
        logger.info(f"Tested by section was found for the jira {jiraNum}")


def getHtmlContent(url):
    try:
        proxies = {
            "http": f"http://{PROXY_USR}:{PROXY_PSW}@{PROXY_HOST}:{PROXY_PORT}",
            "https": f"http://{PROXY_USR}:{PROXY_PSW}@{PROXY_HOST}:{PROXY_PORT}"
        }
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            confluence_response = requests.get(url, auth=(JIRA_USER, decrypt_token()), proxies=proxies, verify=False)

        if not confluence_response.ok:
            message = f"[FAIL] HTTP call to {confluence_response.url} failed and the return status code is" \
                f" {confluence_response.status_code}. \n"
            logger.error(message)
            verification_result['message'] += f"{message}"
            verification_result['verified'] = False
            return None
        else:
            message = f"[PASS] HTTP call to {confluence_response.url} passed and the return status code is " \
                f"{confluence_response.status_code}. \n"
            verification_result['verified'] = True
            verification_result['message'] += f"{message}"
            return confluence_response

    except Exception as e:
        error_message = f"[FAIL] Confluence api call to get the {confluence_response.url}" \
            f" page failed and the exception is {e} \n "
        logger.error(error_message)
        verification_result['verified'] = False
        verification_result['message'] += error_message
        return None


def check_ids(html_content):
    """Verify in Function Section if ID column is not empty"""
    global testStories

    soup = BeautifulSoup(html_content, 'lxml')
    # soup = BeautifulSoup(html_content, 'html.parser')
    functional_table = table_search(soup, "Functional Table", 'Notes on functional')
    print('debug', functional_table)
    required = soup.find_all("a", {"class": "jira-issue-key"})
    print('required_data', required)
    time.sleep(2000)
    if not functional_table:
        error_message = f"[FAIL] The functional table is not present \n"
        verification_result['verified'] = False
        verification_result['message'] += error_message
    else:
        logger.info(
            f"Number of rows in the Functional table:  {len(functional_table.find_all('tr'))}")
        idFound = validIdFound = 0
        print('debug1')
        for row in functional_table.find_all('tr'):
            cell_data = row.find_all('td')
            print("cell_data", cell_data)
            if cell_data != []:
                ID = BeautifulSoup(str(cell_data[0]), "html.parser").text
                print('debug Id', ID)
                if ID != "":
                    if ID == "ID":
                        continue
                    else:
                        idFound += 1
                        if cell_data[0].find('a'):

                            link = cell_data[0].find('a').get('href')
                            print('link', link)
                            if 'https://pappa30l:8443/browse/' in link:
                                validIdFound += 1
                                logger.info(f"Valid Id {link} found in the Id column in confluence page")
                                jiraStory_response = getHtmlContent(link)
                                if jiraStory_response:
                                    parseJiraStory(jiraStory_response.text, link)

        if testStories:
            testStories = list(dict.fromkeys(testStories))
            print("test_stories", testStories)
            for testStory in testStories:
                print('test_story', testStory)
                parseZephyrtestcases(testStory)
        else:
            error_message = f"[FAIL] No TEST cases were found for the ID found in functional table \n"
            verification_result['verified'] = False
            verification_result['message'] += error_message

        if idFound == 0:
            error_message = f"[FAIL] The functional table has no ID listed or functional table is empty \n"
            verification_result['verified'] = False
            verification_result['message'] += error_message

        elif idFound != 0 and validIdFound == 0:
            error_message = f"[FAIL] The functional table has invalid IDs listed \n"
            verification_result['verified'] = False
            verification_result['message'] += error_message

        elif idFound != 0 and validIdFound != idFound:
            error_message = f"[FAIL] The functional table has some invalid IDs listed \n"
            verification_result['verified'] = False
            verification_result['message'] += error_message

        elif idFound != 0 and validIdFound == idFound:
            pass_message = f"[PASS] The functional table has IDs listed with valid Links \n"
            verification_result['verified'] = True
            verification_result['message'] += pass_message

    return verification_result


def verify():
    global verification_result
    #set_rule_version()
    confluence_api_url = "https://occprod.atlassian.net/wiki/spaces/RITA/pages/17871799666/Stock+Loan+Q2+Cycle4+Test+Scope"
    confluence_response = getHtmlContent(confluence_api_url)
    if confluence_response:
        check_ids(confluence_response.text)

    checks_failed = 0
    for message in verification_result['message'].split('\n'):
        if "[FAIL]" in message:
            checks_failed += 1

    if checks_failed >= 1:
        verification_result['verified'] = False

    return verification_result

ZEPHYR_API_URL = "rest/zapi/latest/zql/executeSearch?zqlQuery=issue="
JIRA_USER = 'srvc_jira_api_rest@theocc.com'
JIRA_ISSUE_ID = 'GOO-1157'
JIRA_API_URL = 'https://occprod.atlassian.net/'
PROXY_HOST = 'prodproxy.theocc.com'
PROXY_PORT = '8060'
PROXY_USR = 'srvc_prxy_zephyr'
PROXY_PSW = 'eXNsjT8gtA9FUz3'
issue = 'GOO-1157'
RESULT_OUTPUT_PATH ="C:\\Users\\SMAKA01\\ORGREPO\\verify-rit-test-execution\\src\\result.json"
MID_URL = 'rest/api/3/issue/'
cert_path = '/occ/certificates/pappa30l.theocc.com.pem'


# ZEPHYR_API_URL = "rest/zapi/latest/zql/executeSearch?zqlQuery=issue="
# JIRA_API_URL = "https://pappa30l:8443"
# confluence_user = get_from_environment("JIRA_USERNAME")
# confluence_password = get_from_environment("JIRA_PASSWORD")
# confluence_api_url = os.environ.get("TEST_SCOPE_URL")
# RESULT_OUTPUT_PATH = os.environ.get("RESULT_OUTPUT_PATH", "/occ/output/result.json")
# logger.info(f"confluence_user   = {confluence_user}")
# logger.info(f"TEST_SCOPE_URL = {confluence_api_url}")
testStories = []


def main():
    global testStories
    # set_jira_api_url()
    with open(RESULT_OUTPUT_PATH, 'w') as f:
        f.write(json.dumps(verify(), indent=4))
    logger.info(f"results are also written to '{RESULT_OUTPUT_PATH}'")


if __name__ == "__main__":
    main()
