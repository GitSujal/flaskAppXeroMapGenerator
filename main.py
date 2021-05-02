
from flask import Flask
from flask import render_template

from flask_caching import Cache

from flask import Flask, request, redirect,send_file

from xero.auth import OAuth2Credentials
from transport import XeroApiWrapper

from datetime import datetime
import os
import pandas as pd

import glob

import json
import sys

def loadconfig(configfile):
    if configfile is None:
        configfile="config.json"
    with open(configfile, 'r') as f:
        config = json.load(f)
        client_id = config['client_id']
        client_secret = config['client_secret']
        callback_uri=config['callback_uri']
    return client_id,client_secret,callback_uri


cache_config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 5000
}

app = Flask(__name__)

app.config.from_mapping(cache_config)
cache = Cache(app)

configfile=None
if len(sys.argv)>1:
    configfile=sys.argv[1]

client_id,client_secret,callback_uri=loadconfig(configfile=configfile)
credentials = OAuth2Credentials(client_id, client_secret,callback_uri=callback_uri)


def writedicttocsv(dict_name,csvfilename):
    df = pd.DataFrame.from_dict(dict_name)
    df.to_csv(csvfilename, header=True,index=False)


@app.route('/')
def root():    
    return render_template('index.html')


@app.route('/xero/oauth2')
def xero_oauth2():
    credentials = OAuth2Credentials(client_id, client_secret, callback_uri=callback_uri)
    authorization_url = credentials.generate_url()
 
    cache.set('xero_creds',credentials.state)

    return redirect(authorization_url)

@app.route('/xero/callback')
def xero_callback():

    cred_state = cache.get('xero_creds')
    credentials = OAuth2Credentials(**cred_state)
    auth_secret = request.url
    credentials.verify(auth_secret)
    credentials.set_default_tenant()
    cache.set('xero_creds',credentials.state)
    return redirect('/xero')

@app.route('/xero')
def xero_view():
    
    cred_state = cache.get('xero_creds')
    credentials = OAuth2Credentials(**cred_state)
    if credentials.expired():
        credentials.refresh()
        cred_state = cache.get('xero_creds')
        credentials = OAuth2Credentials(**cred_state)

    cache.set('xero_creds',credentials.state)
    xero = XeroApiWrapper(credentials=credentials)

    my_groups = xero.contactgroups.all()
    my_contact_groups_name = [x['Name'] for x in my_groups]

    my_contact_groups_name = list( dict.fromkeys(my_contact_groups_name))  # Remove duplicates
    
    cache.set('default_select_group',my_groups[0])

    postal_regions = [cont['Addresses'][0]["Region"].strip() for cont in xero.contacts.all()]
    postal_regions = list( dict.fromkeys(postal_regions))
    postal_regions.append("All") # Select all options

    cache.set('success'," ")

    return render_template('xero.html',contact_group_list=my_contact_groups_name,postal_states_list=postal_regions,success_message=cache.get('success'))


@app.route('/xero',methods=['POST'])
def xero_view_form():
    
    default_name = cache.get('default_select_group')
    group = request.form.get('group_option', default_name) 
    
    default_state= "All"
    state = request.form.get('states_option', default_state)

    cred_state = cache.get('xero_creds')
    credentials = OAuth2Credentials(**cred_state)
    if credentials.expired():
        credentials.refresh()
        cred_state = cache.get('xero_creds')
        credentials = OAuth2Credentials(**cred_state)

    cache.set('xero_creds',credentials.state)

    xero = XeroApiWrapper(credentials=credentials)

    towritedict = {
        "Name":[]
        ,"AddressLine":[]
        ,"AddressArea":[]
        ,"AddressPostcode":[]
        ,"AddressState":[]
        ,"AddressCountry":[]
        ,"Phone":[]
        ,"EmailAddress":[]
    }

    map_contacts = xero.get_contacts_in_group_names(names=[group], limit=None)
    
    if state!="All":
        for contact in map_contacts:
            x = contact.flatten_verbose()
            if 'Region' in x['MAIN Address'].keys() and x['MAIN Address']['Region'].strip() != state:
                pass
            else:
                map_contacts.remove(contact)

    for contact in map_contacts:

        x = contact.flatten_verbose()
        
        # Checking for full address and phone number
        if 'AddressLine1' in x['MAIN Address'].keys() and 'PhoneNumber' in x['MAIN Phone'].keys():
            towritedict["Name"].append(x["Name"])
            towritedict["EmailAddress"].append(x["EmailAddress"])
            towritedict["AddressLine"].append(x['MAIN Address']['AddressLine1'])
            towritedict["AddressArea"].append(x['MAIN Address']['City'])
            towritedict["AddressState"].append(x['MAIN Address']['Region'])
            towritedict["AddressPostcode"].append(x['MAIN Address']['PostalCode'])
            towritedict["AddressCountry"].append(x['MAIN Address']['Country'])
            towritedict["Phone"].append(x['MAIN Phone']['PhoneAreaCode']+ " " + x['MAIN Phone']['PhoneNumber'])


    now = datetime.now()
    
    filename = "export"+str(group)+"_"+now.strftime("%d_%b_%Y_%I_%M_%S_%p")+".csv"
    directory=os.getcwd()+ "/dump/"
    full_path = directory+filename
    
    files = glob.glob('directory'+'*.csv')
    for f in files:
        try:
            os.remove(f)
        except OSError as e:
            print("Error: %s : %s" % (f, e.strerror))


    writedicttocsv(dict_name=towritedict,csvfilename=full_path)
    cache.set('download_file',full_path)
    cache.set('file_name',filename)
    cache.set('success',"CSV File Downloaded")
    return redirect('/download',code=302)

@app.route('/download')
def download_file():
    csv_path  = cache.get('download_file')
    filename=cache.get('file_name')
    return send_file(csv_path, attachment_filename=filename,as_attachment=True)


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host='127.0.0.1', port=8000, debug=True,ssl_context='adhoc')

