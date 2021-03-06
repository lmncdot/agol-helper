import httplib
import urlparse
import os
import sys
import shutil
import json
from xml.etree import ElementTree as ET
import arcpy
import mimetypes
from arcpy import mapping
from arcpy import env
from base import BaseAGOLClass
class AGOL(BaseAGOLClass):
    """ publishes to AGOL """
    _username = None
    _password = None
    _token = None
    _url = "http://www.arcgis.com/sharing/rest"
    def __init__(self, username, password, token_url=None):
        """ constructor """
        self._username = username
        self._password = password
        if token_url is None:
            self._token = self.generate_token()[0]
        else:
            self._token = self.generate_token()[0]
    #----------------------------------------------------------------------
    @property
    def contentRootURL(self):
        """ returns the Portal's content root """
        return self._url + "/content"
    #----------------------------------------------------------------------
    def addComment(self, item_id, comment):
        """ adds a comment to a given item.  Must be authenticated """
        url = self.contentRootURL + "/items/%s/addComment" % item_id
        params = {
            "f" : "json",
            "comment" : comment,
            "token" : self._token
        }
        return self._do_post(url, params)
    #----------------------------------------------------------------------
    def addRating(self, item_id, rating=5.0):
        """Adds a rating to an item between 1.0 and 5.0"""
        if rating > 5.0:
            rating = 5.0
        elif rating < 1.0:
            rating = 1.0
        url = self.contentRootURL + "/items/%s/addRating" % item_id
        params = {
            "f": "json",
            "token" : self._token,
            "rating" : "%s" % rating
        }
        return self._do_post(url, params)
    #----------------------------------------------------------------------
    def createFolder(self, folder_name):
        """ creats a folder for a user's agol account """
        url = self.contentRootURL + "/users/%s/createFolder" % self._username
        params = {
            "f" : "json",
            "token" : self._token,
            "title" : folder_name
        }
        return self._do_post(url, params)
    #----------------------------------------------------------------------
    def deleteFolder(self, item_id):
        """ deletes a user's folder """
        url = self.contentRootURL + "/users/%s/%s/delete" % (self._username, item_id)
        params = {
            "f" : "json",
            "token" : self._token
        }
        return self._do_post(url, params)
    #----------------------------------------------------------------------
    def item(self, item_id):
        """ returns information about an item on agol/portal """
        params = {
            "f" : "json",
            "token" : self._token
        }
        url = self.contentRootURL + "/items/%s" % item_id
        return self._do_get(url, params)
    #----------------------------------------------------------------------
    def _prep_mxd(self, mxd):
        """ ensures the requires mxd properties are set to something """
        changed = False
        if mxd.author.strip() == "":
            mxd.author = "NA"
            changed = True
        if mxd.credits.strip() == "":
            mxd.credits = "NA"
            changed = True
        if mxd.description.strip() == "":
            mxd.description = "NA"
            changed = True
        if mxd.summary.strip() == "":
            mxd.summary = "NA"
            changed = True
        if mxd.tags.strip() == "":
            mxd.tags = "NA"
            changed = True
        if mxd.title.strip() == "":
            mxd.title = "NA"
            changed = True
        if changed == True:
            mxd.save()
        return mxd
    #----------------------------------------------------------------------
    def getUserContent(self):
        """ gets a user's content on agol """
        data = {"token": self._token,
                "f": "json"}
        url = "http://www.arcgis.com/sharing/content/users/%s" % (self._username,)
        jres = self._do_get(url=url, param_dict=data, header={"Accept-Encoding":""})
        return jres
    def getUserInfo(self):
        """ gets a user's info on agol """
        data = {"token": self._token,
                "f": "json"}
        url = "http://www.arcgis.com/sharing/rest/community/users/%s" % (self._username,)
        jres = self._do_get(url=url, param_dict=data, header={"Accept-Encoding":""})
        return jres

    #----------------------------------------------------------------------
    def addFile(self, file_path, agol_type, name, tags, description):
        """ loads a file to AGOL """
        params = {
                    "f" : "json",
                    "filename" : os.path.basename(file_path),
                    "type" : agol_type,
                    "title" : name,
                    "tags" : tags,
                    "description" : description
                }
        if self._token is not None:
            params['token'] = self._token
        url = "{}/content/users/{}/addItem".format(self._url,
                                                   self._username)
        parsed = urlparse.urlparse(url)
        files = []
        files.append(('file', file_path, os.path.basename(file_path)))

        res = self._post_multipart(host=parsed.hostname,
                                   selector=parsed.path,
                                   files = files,
                                   fields=params,
                                   ssl=parsed.scheme.lower() == 'https')
        res = self._unicode_convert(json.loads(res))
        return res
    #----------------------------------------------------------------------
    def deleteItem(self, item_id):
        """ deletes an agol item by it's ID """
        deleteURL = '{}/content/users/{}/items/{}/delete'.format(self._url, self._username, item_id)
        query_dict = {'f': 'json',
                      'token': self._token}
        jres = self._do_post(deleteURL, query_dict)
        return jres
    #----------------------------------------------------------------------
    def _modify_sddraft(self, sddraft,maxRecordCount='1000'):
        """ modifies the sddraft for agol publishing """

        doc = ET.parse(sddraft)

        root_elem = doc.getroot()
        if root_elem.tag != "SVCManifest":
            raise ValueError("Root tag is incorrect. Is {} a .sddraft file?".format(sddraft))

        # The following 6 code pieces modify the SDDraft from a new MapService
        # with caching capabilities to a FeatureService with Query,Create,
        # Update,Delete,Uploads,Editing capabilities as well as the ability to set the max
        # records on the service.
        # The first two lines (commented out) are no longer necessary as the FS
        # is now being deleted and re-published, not truly overwritten as is the
        # case when publishing from Desktop.
        # The last three pieces change Map to Feature Service, disable caching
        # and set appropriate capabilities. You can customize the capabilities by
        # removing items.
        # Note you cannot disable Query from a Feature Service.

        # Change service type from map service to feature service
        for desc in doc.findall('Type'):
            if desc.text == "esriServiceDefinitionType_New":
                desc.text = 'esriServiceDefinitionType_Replacement'

        for config in doc.findall("./Configurations/SVCConfiguration/TypeName"):
            if config.text == "MapServer":
                config.text = "FeatureServer"

        #Turn off caching
        for prop in doc.findall("./Configurations/SVCConfiguration/Definition/" +
                                    "ConfigurationProperties/PropertyArray/" +
                                    "PropertySetProperty"):
            if prop.find("Key").text == 'isCached':
                prop.find("Value").text = "false"
            if prop.find("Key").text == 'maxRecordCount':
                prop.find("Value").text = maxRecordCount

        for prop in doc.findall("./Configurations/SVCConfiguration/Definition/Extensions/SVCExtension"):
            if prop.find("TypeName").text == 'KmlServer':
                prop.find("Enabled").text = "false"

        # Turn on feature access capabilities
        for prop in doc.findall("./Configurations/SVCConfiguration/Definition/Info/PropertyArray/PropertySetProperty"):
            if prop.find("Key").text == 'WebCapabilities':
                prop.find("Value").text = "Query,Create,Update,Delete,Uploads,Editing,Sync"

        # Add the namespaces which get stripped, back into the .SD
        root_elem.attrib["xmlns:typens"] = 'http://www.esri.com/schemas/ArcGIS/10.1'
        root_elem.attrib["xmlns:xs"] = 'http://www.w3.org/2001/XMLSchema'
        newSDdraft = os.path.dirname(sddraft) + os.sep + "draft_mod.sddraft"
        # Write the new draft to disk
        with open(newSDdraft, 'w') as f:
            doc.write(f, 'utf-8')
        del doc
        return newSDdraft
    #----------------------------------------------------------------------
    def _upload_sd_file(self, sd, service_name, tags="None", description="None"):
        """ uploads the sd file to agol """
        url = "{}/content/users/{}/addItem".format(self._url,
                                                   self._username)
        params = {
            "f" : "json",
            "token" : self._token,
            "filename" : os.path.basename(sd),
            "type" : "Service Definition",
            "title" : service_name,
            "tags" : tags,
            "description" : description

        }
        vals =self.addFile(file_path=sd,
                     agol_type="Service Definition",
                     name=service_name,
                     tags=tags,
                     description=description)
        if "success" in vals:
            return vals['id']
        else:
            return "Error Uploadings"
    #----------------------------------------------------------------------
    def enableSharing(self, agol_id, everyone='true', orgs='true', groups='None'):
        """ changes an items sharing permissions """
        share_url = '{}/content/users/{}/items/{}/share'.format(self._url,
                                                               self._username,
                                                               agol_id)
        if groups == None:
            groups = ''
        query_dict = {'f': 'json',
                      'everyone' : everyone,
                      'org' : orgs,
                      'groups' : groups,
                      'token': self._token}
        vals = self._do_post(share_url, query_dict)
        return vals
    def updateTitle(self, agol_id, title):
        """ changes an items title"""
        share_url = '{}/content/users/{}/items/{}/update'.format(self._url,
                                                               self._username,
                                                               agol_id)

        query_dict = {'f': 'json',
                      'title' : title,
                      'token': self._token}
        vals = self._do_post(share_url, query_dict)
        return vals
    def delete_items(self,items):
        content = self.getUserContent()
        #Title, item
        for item in content['items']:
            if item['title'] in items:
                print "Deleted: " + self._tostr(self.deleteItem(item['id']))
    #----------------------------------------------------------------------
    def publish_to_agol(self, mxd_path, service_name="None", tags="None", description="None"):
        """ publishes a service to AGOL """
        mxd = mapping.MapDocument(mxd_path)
        sddraftFolder = env.scratchFolder + os.sep + "draft"
        sdFolder = env.scratchFolder + os.sep + "sd"
        sddraft = sddraftFolder + os.sep + service_name + ".sddraft"
        sd = sdFolder + os.sep + "%s.sd" % service_name
        mxd = self._prep_mxd(mxd)

        if service_name == "None":
            service_name = mxd.title.strip().replace(' ','_')
        if tags == "None":
            tags = mxd.tags.strip()
        if description == "None":
            description = mxd.description.strip()

        if os.path.isdir(sddraftFolder) == False:
            os.makedirs(sddraftFolder)
        else:
            shutil.rmtree(sddraftFolder, ignore_errors=True)
            os.makedirs(sddraftFolder)
        if os.path.isfile(sddraft):
            os.remove(sddraft)
        analysis = mapping.CreateMapSDDraft(mxd, sddraft,
                                            service_name,
                                            "MY_HOSTED_SERVICES")
        sddraft = self._modify_sddraft(sddraft)
        analysis = mapping.AnalyzeForSD(sddraft)
        if os.path.isdir(sdFolder):
            shutil.rmtree(sdFolder, ignore_errors=True)
            os.makedirs(sdFolder)
        else:
            os.makedirs(sdFolder)
        if analysis['errors'] == {}:
            # Stage the service
            arcpy.StageService_server(sddraft, sd)
            print "Created {}".format(sd)

        else:
            # If the sddraft analysis contained errors, display them and quit.
            print analysis['errors']
            sys.exit()
        # POST data to site
        content = self.getUserContent()
        #Title, item
        for item in content['items']:
            if item['title'] == service_name and \
               item['item'] == os.path.basename(sd):
                 print "Deleted: " + self._tostr( self.deleteItem(item['id']))

            elif item['title'] == service_name:
                 print "Deleted: " + self._tostr( self.deleteItem(item['id']))

        self._agol_id = self._upload_sd_file(sd, service_name=service_name,
                                             tags=tags, description=description)
        del mxd
        if self._agol_id != "Error Uploadings":
            p_vals = self._publish(agol_id=self._agol_id)
            if 'error' in p_vals:
               raise ValueError(p_vals)

            for service in p_vals['services']:
                if 'error' in service:
                    raise ValueError(service)



                return service['serviceItemId']
            del p_vals

    #----------------------------------------------------------------------
    def _publish(self, agol_id):
        """"""
        publishURL = '{}/content/users/{}/publish'.format(self._url,
                                       self._username)



        query_dict = {'itemID': agol_id,
                     'filetype': 'serviceDefinition',
                     'f': 'json',
                     'token': self._token
                     }

        return self._do_post(publishURL, query_dict)
    #----------------------------------------------------------------------
##    def searchGroups(self,q=None, start='1',num=1000,sortField='',
##               sortOrder='asc'):
##        query_dict = {
##            "f" : "json",
##            "token" : self._token,
##            "q": q,
##            "start": start,
##            "num": num,
##            "sortField": sortField,
##            "sortOrder": sortOrder
##        }
##        groupsURL = self._url + "community/groups"
##        return self._do_post(groupsURL, query_dict)

    def createGroup(self, title, description, tags,
                    snippet=None, phone=None,
                    access="org", sortField=None, sortOrder=None,
                    isViewOnly=False, isInvitationOnly=False,
                    thumbnail=None):
        """
           The Create Group operation creates a new group in the Portal
           community.
           Only authenticated users can create groups. The user who creates
           the group automatically becomes the owner of the group. The
           owner of the group is automatically an administrator of the
           group. The calling user provides the title for the group, while
           the group ID is generated by the system.
           Inputs:
              title - The group title must be unique for the username, and
                      the character limit is 250.
              description - A description of the group that can be any
                            length.
              tags - Tags are words or short phrases that describe the
                     group. Separate terms with commas.
              snippet - Snippet or summary of the group that has a
                        character limit of 250 characters.
              phone - Phone is the group contact information. It can be a
                      combination of letters and numbers. The character
                      limit is 250.
              access - sets the access level for the group. private is the
                       default. Setting to org restricts group access to
                       members of your organization. If public, all users
                       can access the group.
                       Values: private | org |public
              sortField - Sets sort field for group items.
              sortOrder - Sets sort order for group items.
              isViewOnly - Allows the group owner or admin to create
                           view-only groups where members are not able to
                           share items. If members try to share, view-only
                           groups are returned in the notshared response
                           property. false is the default.
              isInvitationOnly - If true, this group will not accept join
                                 requests. If false, this group does not
                                 require an invitation to join. Only group
                                 owners and admins can invite users to the
                                 group. false is the default.
              thumbnail - Enter the pathname to the thumbnail image to be
                          used for the group. The recommended image size is
                          200 pixels wide by 133 pixels high. Acceptable
                          image formats are PNG, GIF, and JPEG. The maximum
                          file size for an image is 1 MB. This is not a
                          reference to the file but the file itself, which
                          will be stored in the Portal.
        """
        params = {
            "f" : "json",
            "token" : self._token,
            "title" : title,
            "description" : description,
            "tags" : tags,
            "access" : access,
            "isViewOnly" : isViewOnly,
            "isInvitationOnly" : isInvitationOnly
        }
        uURL = self._url + "/community/createGroup"
        if snippet is not None:
            params['snippet'] = snippet
        if phone is not None:
            params['phone'] = phone
        if sortField is not None:
            params['sortField'] = sortField
        if sortOrder is not None:
            params['sortOrder'] = sortOrder
        if thumbnail is not None and \
           os.path.isfile(thumbnail):

            params['thumbnail'] = os.path.basename(thumbnail)
            content = open(thumbnail, 'rb').read()
            parsed = urlparse.urlparse(uURL)
            port = parsed.port
            files = []
            files.append(('thumbnail', thumbnail, os.path.basename(thumbnail)))

            return self._post_multipart(host=parsed.hostname,
                                       selector=parsed.path,
                                       fields=params,
                                       files=files,
                                       ssl=parsed.scheme.lower() == 'https')

        else:
            return self._do_post(url=uURL, param_dict=params)




# This function is a workaround to deal with what's typically described as a
# problem with the web server closing a connection. This is problem
# experienced with www.arcgis.com (first encountered 12/13/2012). The problem
# and workaround is described here:
# http://bobrochel.blogspot.com/2010/11/bad-servers-chunked-encoding-and.html
def patch_http_response_read(func):
    def inner(*args):
        try:
            return func(*args)
        except httplib.IncompleteRead, e:
            return e.partial

    return inner
httplib.HTTPResponse.read = patch_http_response_read(httplib.HTTPResponse.read)

