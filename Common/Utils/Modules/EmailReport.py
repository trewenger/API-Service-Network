"""
Docstring for Common.Utils.Modules.EmailReport
Purpose: 
-   This module is used for a the standard report generation and email pipeline.
-   Running this module will query Fishbowl for the report data, then email it to the desired recipient. 
-   This module is still a work in progress and likely won't function as intended. 
"""

from Fishbowl.FishbowlSession import FishbowlSession
from Fishbowl.Queries import *
from Email.EmailApi import *
import pandas
import os
from datetime import datetime
from pathlib import Path

# Configs
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))  # path to save the csv output
REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_FOLDER = REPO_ROOT / "CSV"
TODAY = (datetime.now()).strftime("%m/%d/%Y")

# Globals:
error_flag = 0
logs = {}

#-------------------------- Get Fishbowl Data -------------------------------#

def get_fb_data(query) -> None:
    """
    Retrieves Fishbowl query data and returns it.
    """

    try:
        log("get_fb_data", "Logging in to Fishbowl. ")
        session = FishbowlSession()
        log("get_fb_data", "Querying report... ")
        ytd_shipped = session.query(query)
        log("get_fb_data", "Logging out. ")
        session.logout()
        log("get_fb_data", "Success. Fishbowl query collected and session logged out. ")
        return ytd_shipped
    except Exception as e:
        log("get_fb_data", e, True)
        log("get_fb_data", "Failed to get query data. Ending call stack. ", True)
        return e

#-------------------------- Write to CSV ------------------------------------#

def csv_export(data, filename) -> None:
    """
    Removes the previous CSV file from the CSV folder, then exports the new CSV file. Returns the file path.
    """

    try:
        if not filename:
            filename = "default.csv"
        if filename[-4:] != ".csv":
            print(f"not a csv file!! the last 4 characters != .csv: {filename[-4]}")
            filename = f"{filename}.csv"
        # CSV Names
        log("csv_export", "Setting file paths for CSV files based on current PC. ")
        csv_file = os.path.join(CSV_FOLDER, filename)

        # Removing old CSV files. 
        log("csv_export", "Deleting old CSV files")
        if os.path.exists(csv_file):
            os.remove(csv_file)
    except Exception as e:
        log("csv_export", "Failed to remove previously existing CSV exports. ", True)
        log("csv_export", e, True)

    try:
        log("csv_export", "Exporting query as CSV. ")
        headers = data[0].keys()
        framed = pandas.DataFrame(data, columns=headers)
        framed.to_csv(csv_file, index=False)  # index=False omits the row numbers
        log("csv_export", f"Success. CSV file exported: {filename} ")
        return csv_file
    except Exception as e:
        log("csv_export", "Failed to export the CSV files", True)
        log("csv_export", e, True)
        return None

#-------------------------Misc Functions -----------------------------------#

def log(func_name:str, message:str, is_error:bool = False) -> None:
    """
    Adjusts the global logs variable to track function specific run results. Set the is_error param 
    to True to change the global error_flag to 1. 
    """

    print(message)

    if is_error:
        global error_flag
        error_flag = 1

    global logs
    if func_name not in logs:
        logs[str(func_name)] = []
    logs[str(func_name)].append(str(message))

def summary_email(subject:str, body:str, recipients:list, error_subject:str, error_recipients:list=[], attachment_path:str=None) -> None:
    """
    Sends an email with attachements.
    """
    
    global error_flag
    if error_flag == 1:
        print()
        log("System", "Errors encountered during run. Sending error summary email.", True)
        print()
        
        email_subject = error_subject
        email_body = ""
        email_rec = error_recipients
        
        global logs
        email_body += "<ol>"
        for key in logs:
            email_body += ("<li><b>" + str(key) + "</b></li><ul>")
            for msg in logs[key]:
                if msg is not None and msg != "":
                    email_body += ("<li>" + str(msg) + "</li>")
            email_body += "</ul>"
        email_body += "</ol>"
        send_email(email_subject, email_body, email_rec)

    else:
        print()
        log("System", "API completed with no errors. Sending run summary email. ")
        print()
        email_subject = subject
        email_rec = recipients
        email_body = body

        send_email(email_subject, email_body, email_rec, attachment_path)

#-------------------------------------------------------------------------------#

def execute(query:str, filename:str, subject:str, body:str, recipients:list, 
            error_subject:str, error_recipients:list=[]):
    """ Runs a query against the Fishbowl DB, saves it as a CSV, and then sends the csv over email. Sends a run
     summary email if the call fails.  """
    # Runs each function if there are no logged errors. 
    global error_flag
    data = get_fb_data(query)

    if error_flag == 0 and data:
        csv_file_path = csv_export(data, filename)
    
    if error_flag == 0 and data:
        summary_email(subject, body, recipients, error_subject, error_recipients, [csv_file_path])
    
    if error_flag == 1:
        summary_email(subject, body, recipients, error_subject, error_recipients)

if __name__ == "__main__":
    execute()
