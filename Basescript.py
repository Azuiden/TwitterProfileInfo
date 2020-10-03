import gspread
from oauth2client.service_account import ServiceAccountCredentials #to authorize gspread
import tweepy   #Python wrapper around Twitter API
import json
from datetime import date
from datetime import datetime
import time
from selenium import webdriver #web driver
import chromedriver_binary
from bs4 import BeautifulSoup #parse html
from urllib.request import urlopen #open urls
import os
import pathlib
import re
import config

begin_time = datetime.now() 

# Connect to Twitter API using the secrets
auth = tweepy.OAuthHandler(config.api_key, config.api_secret_key)
auth.set_access_token(config.access_token, config.access_token_secret)
api = tweepy.API(auth)

def save_json(save_path, file_content):
  with open(save_path, 'w', encoding='utf-8') as data:
    json.dump(file_content, data, ensure_ascii=False, indent=4)

def load_json (load_path):
    #function to load json file
    with open(load_path, 'r', encoding='utf-8') as data:
        load_json = json.load(data)
        return load_json

def limit_handled(cursor, list_name):
  while True:
    try:
      yield cursor.next()
    # Catch Twitter API rate limit exception and wait for 15 minutes
    except tweepy.RateLimitError:
      print("\nData points in list = {}".format(len(list_name)))
      print('Hit Twitter API rate limit.')
      for i in range(3, 0, -1):
        print("Wait for {} mins.".format(i * 5))
        time.sleep(5 * 60)
    # Catch any other Twitter API exceptions
    except tweepy.error.TweepError:
      print('\nCaught TweepError exception' )
    except StopIteration:
        break

def get_followers(pullfollowers_from,followlist):
    cursor = tweepy.Cursor(api.followers, id=pullfollowers_from, count=200).pages()
    users = []
    #iterator to pull follower info from pullfollowers_from variable and store in list
    for i, user in enumerate(limit_handled(cursor,users)):
        print ('Getting page {} for followers'.format(i))
        users += user
    
    users = [x._json for x in users]        # Extract the follower information
    save_json(followlist, users) # Save the data in a JSON file

def birth_hidden (screen_name,path,driver):
    url = "https://twitter.com/" + screen_name #URL of the profile currently being looked at (screen_name)
    try:
        driver.get(url) #driver opens the URL

        soup = BeautifulSoup(urlopen(url),"html.parser") #Beautifulsoup set to parse the html of the URL
        getprofinfo = soup.find('span', class_ = 'ProfileHeaderCard-birthdateText u-dir') #Finds where the birthday is stored in the html
        #If the profile has their birthday hidden, then theres no text to pull so an if statement is required
        if getprofinfo.text.strip() == "":
            birthday = 'Hidden' #If there is no text, set birthday as 'Hidden'
        else:
            birthday = getprofinfo.text.strip() #If there is text, set that as birthday
    except:
        birthday = 'Unexpected error'
    
    return birthday

def worksheetcheck(spreadsheet,rowstoadd):
    #This function checks if there is a worksheet named with today's date (Ymd)
    #If there is, use that worksheet
    #If there isn't, create a worksheet named after the date
    sh = gspread.service_account().open(spreadsheet)
    today = date.strftime(date.today(),"%Y%m%d")
    worksheet_list = sh.worksheets()
    x = 0

    #This is the format that .worksheets() pulls info as from a spreadsheet:
    #[<Worksheet 'sheet1 name' id:0>, <Worksheet 'sheet2 name' id:1032348962>]

    for i in worksheet_list:
        if i.title == today:
            #if worksheet title matches today's date, set x as 1
            x = 1
        else:
            #otherwise do nothing
            continue
    
    #If x is 1 then we know that there is a match, at which point we can choose to use that sheet or create one
    if x == 1:
        worksheet = sh.worksheet(today)
    else:
        worksheet = sh.add_worksheet(title=today, rows=str(rowstoadd), cols="20")
    
    return worksheet    

def createlist (followlist,path,pullfollowers_from):
    options = webdriver.ChromeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    driver = webdriver.Chrome(path, options=options)
    
    row = 3
    x = 0
    profiles_listdict = [
        {
            'range' : 'A1:B1',
            'values' : [[
                'LIST PULLED FROM:', str(pullfollowers_from)
            ]]
        },
        {
        'range' : 'A2:F2',
        'values' : [[
            'ID', 'Screen Name', 'Name', 'Location', 'Description', 'Born'
            ]]
        }
    ]

    #Load each profile in the .json file (where followers are stored) into a list of dictionaries
    for profile in load_json(followlist):
        range_tuple = 'A' , str(row) , ':F' , str(row)
        update_range = "".join(range_tuple)
        screen_name = profile["screen_name"]
        
        #Create a dictionary for the profile that matches the format needed for .batch_update() to work
        prof = {
            "range" : update_range, #Will tell .batch_update() which row to put this info into
            "values" : [[
                str(profile["id"]),str(profile["screen_name"]),str(profile["name"]),str(profile["location"]),str(profile["description"]),birth_hidden(screen_name,path,driver)
                ]]
        }
        row += 1
        x += 1
        profiles_listdict.append(prof) #Adds the dictionary to the list

        #stop and wait every 400 rows bc of runtime
        if x == 401:
            save_json(index_path,profiles_listdict)
            print ("On row " + str(row-1) + " of " + str(len(load_json(followlist))))
            x = 0
            for i in range(5, 0, -1):
                print("Wait for {} mins.".format(i))
                time.sleep(60)

    driver.close()

    os.remove(followlist)
    return profiles_listdict

def batchupdate_function(follower_list,gspreadsheet):
    #Enters into worksheet
    x = len(follower_list)
    worksheet = worksheetcheck(gspreadsheet,x)
    worksheet.batch_update(follower_list, value_input_option='USER_ENTERED')
    worksheet.format('A2:F2',{"horizontalAlignment": "CENTER", "textFormat": {"bold": True}}) #formats header rows
    get_indexedtwitter = follower_list[0].get('values'[1],"!!Error: Couldn't find twitterhandle!!")

    print('Followers from ' + get_indexedtwitter +' added to google spreadsheet' + '' + ': ' + str(len(follower_list)-1)) #Print follower number
    print('Script executed in: ' + str(datetime.now() - begin_time)) #Print script runtime

def input_spreadsheetinfo():
    while True:
        prompt_pull = input("Enter spreadsheet file name: ")
        if re.match(r'.*\S.*',prompt_pull):
            print("Is this correct?: " + prompt_pull)
            if confirm_info() == "yes":
                break
            else:
                pass
        else:
            print("Invalid format")
    return prompt_pull

def input_twitterinfo():
    while True:
        prompt_pull = input("Enter Twitter handle:")
        if re.match(r'^(@)\w+$',prompt_pull):
            print("Is this correct?: " + prompt_pull)
            if confirm_info() == "yes":
                break
            else:
                pass
        else:
            print("Invalid format")
    return prompt_pull
            
def confirm_info():
    while True:
        prompt_confirm = input("Y/N: ")
        if re.match(r'^(?:Y|N\b)', prompt_confirm, re.IGNORECASE):
                if re.match(r'^(?:Y\b)', prompt_confirm, re.IGNORECASE):
                    answer = "yes"
                    return answer
                else:
                    answer = "no"
                    return answer
        else:
            print("Invalid format")

def executionoptions():
    print("Pick one of the following and enter cooresponding number to execute:\n1   Pull followers from specified twitter profile then store data\n2   Upload stored data to google docs")
    while True:
        option_input = input()
        if re.match(r'[1-2]$',option_input):
            if option_input == 1:
                chromedriverpath = config.cdpath
                os.chmod(chromedriverpath, 0o755)

                print("Twitter handle format: @example")
                pullfollowers_from = input_twitterinfo()
                get_followers(pullfollowers_from,followlist_path)
                createlist(followlist_path,chromedriverpath,pullfollowers_from)
            if option_input == 2:
                print("Warning: If there is already a sheet in specified workbook with today's date, this will override the information inside.\n You can avoid this by renaming the sheet or deleting it.")
                spreadsheet_name = input_spreadsheetinfo() #Make sure the google API has access to the googlesheet file
                batchupdate_function(load_json(index_path),spreadsheet_name)
            else:
                print("Error")
                pass
        else:
           print("Invalid format")

if __name__ == '__main__':
    #TODO: 
    # run test on current code
    # Change the indexed_list.json file so that it names it after the inputted twitter handle (Twitterhandle_indexedlist.json)
    # Edit executionoptions() def so that it goes back to top after execution option 1 or 2
    # Option 1 should check the named index files then match to entered data; if named index file exists, it should override it
        #probably have input_twitterinfo() reformat whatever was entered into something uniform if files are case sensitive

    followlist_path = os.path.join(config.file_path,'tempfollowerlist.json')
    index_path = config.file_path + 'indexed_list.json'

    print("You will need to enter the name of your google spreadsheet as well as the Twitter handle of the account you would like to pull follower information from.\nMake sure that the google spreadsheet is shared with the bot, otherwise this will return an error\nShare the spreadsheet with followerlist@twitter-agebot.iam.gserviceaccount.com; access can be revoked immediately after the data had been uploaded.")
    print("---")

    executionoptions()