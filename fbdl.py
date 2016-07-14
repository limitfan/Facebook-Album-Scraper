#  ______             _                 _               _ _                       _____                      _                 _           
# |  ____|           | |               | |        /\   | | |                     |  __ \                    | |               | |          
# | |__ __ _  ___ ___| |__   ___   ___ | | __    /  \  | | |__  _   _ _ __ ___   | |  | | _____      ___ __ | | ___   __ _  __| | ___ _ __ 
# |  __/ _` |/ __/ _ \ '_ \ / _ \ / _ \| |/ /   / /\ \ | | '_ \| | | | '_ ` _ \  | |  | |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|
# | | | (_| | (_|  __/ |_) | (_) | (_) |   <   / ____ \| | |_) | |_| | | | | | | | |__| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |   
# |_|  \__,_|\___\___|_.__/ \___/ \___/|_|\_\ /_/    \_\_|_.__/ \__,_|_| |_| |_| |_____/ \___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|   
#coding=UTF-8
from robobrowser import RoboBrowser
from threading import Thread, Lock
from Queue import Queue
from urllib2 import urlopen, URLError, HTTPError
import time
import urllib2
import sys
import re
import os
import json
import hashlib

UA= "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5 Build/MOB30M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/44.0.2403.119 Mobile Safari/537.36"
fbMain = "https://m.facebook.com"


#Todo: the possibility of many albums exceeding the limit of single mobile page in the album's overview page with a "See All Albums" button

start = 12345
end   = 12445

storage = "FacebookPhotos"

redirect = "home.php?_rdr"
page404 = "Page Not Found"
albumStr = "/albums/"

ntries = 5
defaultTimeout = 5

id2username = {}

albumsPage2id = {}

thumbnailPage2albumPage = {}

fullSize2thumbnail = {}

id2cnt = {}

loginCNT = 30
thumbnailStepCount = 12

#Queues for thread synchronization
id_queue = Queue()
albums_queue = Queue()
thumbnail_queue = Queue()
img_queue = Queue()

#Thread groups for image crawling speed control
num_albums_fetch  = 1

num_thumbnail_fetch = 1

num_fullsize_fetch = 2
num_img_download = 20

browserList = [RoboBrowser(user_agent=UA, timeout=defaultTimeout, tries=ntries) for i in range(num_albums_fetch+num_thumbnail_fetch+num_fullsize_fetch)]

hashStr = {}



#dlBrowser = RoboBrowser(user_agent=UA)
fbUser = ""
fbPassword = ""
isProxyOpen = False

mutex = Lock()
strMutex = Lock()
strcounter = 0
counter = 0
def getCurrentCounter():
    ret = 0
    mutex.acquire()
    global counter
    ret = counter 
    counter = counter + 1
    mutex.release()
    return ret

def getCurrentIndex4ID(currentID):
    mutex.acquire()
    ret = 0
    global id2cnt
    ret = id2cnt[currentID]
    id2cnt[currentID] = ret + 1
    mutex.release()
    return ret

def getMD5sum(text):
    return hashlib.md5(text).hexdigest()

#optimizing memory footprint
def getShortString(longStr):
    tmpstr = getMD5sum(longStr)
    if tmpstr in hashStr:
        return hashStr[tmpstr]
    ret = 0
    strMutex.acquire()
    global strcounter
    ret = strcounter
    strcounter = strcounter + 1
    hashStr[tmpstr] = ret
    strMutex.release()
    return ret

def createDir(currentID):

    dirPath = storage+"[{}_{}]/{}".format(start, end, currentID)
    if not os.path.exists(dirPath):
        os.makedirs(dirPath)

def login2FBmobile():
    #browserList.append(dlBrowser)
    global fbUser
    global fbPassword
    ind = 0
    for browser in browserList:
        mail = fbUser
        password = fbPassword
        browser.open(fbMain)
        form = browser.get_form()
        form['email'].value = mail
        form['pass'].value  = password
        browser.submit_form(form)
        #time.sleep(1)
        print "browser {} has logined in.".format(ind)
        ind = ind + 1
        #print "{} is done.".format(i)

def accessAlbumPage(i, q):
    while True:
        x = q.get()
        print '[Thread:%02d]Album Fetch: Looking for the next id: %s' % (i, x)
        #print "start to access album page with id:{}".format(x)
        currentUserMain = fbMain+"/{}".format(x)
        try:
            browserList[i].open(currentUserMain)
        except Exception as ex:
            print "browser open album homepage exception"
            time.sleep(2)
            continue
        currentUrl = browserList[i].url
      
        # photo_link = browser.get_link('Photos')
        # browser.follow_link(photo_link)
        #print browser.parsed
        #browser.open("https://m.facebook.com/profile.php?v=photos&id={}".format(x))

        q.task_done()
        # if redirect in browser.url:
        #     print "user {} does not exist".format(x)
        #     continue
        if page404 in browserList[i].select('title')[0].text:
            print "user {} does not exist".format(x)
            continue
        s = currentUrl.rfind('/')
        e = currentUrl.find('?')
        id2username[x] = currentUrl[s+1:e]
        albumsUrl = "https://m.facebook.com/{}/photos/albums/?owner_id={}".format(id2username[x], x)
        albums_queue.put(albumsUrl)

        #memory 1
        albumsPage2id[getShortString(albumsUrl)] = x
        print "username:"+currentUrl[s+1:e]
        print "albumsUrl:"+albumsUrl 

        time.sleep(3)

        #print browser.parsed

def accessThumbnail(i, q):
    while True:
        albumsUrl = q.get()
        print '[Thread:%02d]Thumbnail Fetch: Looking for the next album url: %s' % (i, albumsUrl)
        try:
            browserList[num_albums_fetch+i].open(albumsUrl)
        except Exception as ex:
            print "browser open album exception"
            time.sleep(2)
            continue
        print browserList[num_albums_fetch+i].select('a')
        for singleAlbum in browserList[num_albums_fetch+i].select('a'):
            #print "singleAlbum href:"+singleAlbum['href']
            if albumStr in singleAlbum['href']:
                print "accessing thumbnail:"+singleAlbum['href']
                currentIndex = 0
                while True:
                    print "access single album with currentIndex:{}".format(currentIndex)
                    try:
                        browserList[num_albums_fetch+i].open(fbMain+singleAlbum['href']+"?start_index={}".format(currentIndex))
                    except Exception as ex:
                        print "browser open thumbnail exception"
                        time.sleep(2)
                        continue

                    for thumbnail in browserList[num_albums_fetch+i].select('a'):
                        if "photo.php" in thumbnail['href']:
                            print "+++++++++++++++Generating Thumbnail++++++++++++++++"
                            thumbnail_queue.put(thumbnail['href'])
                            #memory 2
                            thumbnailPage2albumPage[getShortString(thumbnail['href'])] = getShortString(albumsUrl)

                    print browserList[num_albums_fetch+i].get_link("More Photos")
                    if browserList[num_albums_fetch+i].get_link("More Photos") is None:
                        print "finishing one single album"
                        break
                    currentIndex += thumbnailStepCount

        q.task_done()


def accessFullsize(i, q):
    while True:
        thumbnailUrl = q.get()
        print '[Thread:%02d]Fullsize Fetch: Looking for the next thumbnail url: %s' % (i, thumbnailUrl)       
        try: 
            browserList[num_albums_fetch+num_thumbnail_fetch+i].open(fbMain+thumbnailUrl)
        except Exception as ex:
            print "browser open fullsize exception"
            time.sleep(2)
            continue

        fullsizeLink = browserList[num_albums_fetch+num_thumbnail_fetch+i].get_link("View Full Size")
        print "fullsize image link:"+fullsizeLink['href']
        img_queue.put(fullsizeLink['href'])
        #memory 3
        print "!!!!!!!!!!!!!!!!!!!!!!!!memory 3:-----{}----{}--------".format(getShortString(fullsizeLink['href']), getShortString(thumbnailUrl))
        fullSize2thumbnail[getShortString(fullsizeLink['href'])] = getShortString(thumbnailUrl)
        q.task_done()

def saveLinktoFile(url, fileName):
    for _ in range(ntries):
        try:
            f = urllib2.urlopen(url, timeout=defaultTimeout)
            #print "downloading " + url

            # Open our local file for writing
            with open(os.path.abspath(fileName), "wb") as local_file:
                local_file.write(f.read())
            break
        #handle errors
        except HTTPError, e:
            print "HTTP Error:", e.code, url
        except URLError, e:
            print "URL Error:", e.reason, 
        except Exception  as ex:
            print "timeout exception"
            time.sleep(2)
            pass
    else:
        print "image is not downloaded"
  
def downloadImage(i, q):
    while True:
        try:
            print '[Thread%02d]Image Fetch: Looking for the next image url with image queue size %s\n' % (i, img_queue.qsize())
            imgUrl = q.get()


            print "===============image url to be downloaded:"+imgUrl
            #print '%s: Downloading:' % i, url
            thumbnailPage = fullSize2thumbnail[getShortString(imgUrl)]
            albumsPage = thumbnailPage2albumPage[thumbnailPage]
            currentID = albumsPage2id[albumsPage]

            print "@@@@@@@@@@@@@@@@@@----{}-----{}------{}-------".format(thumbnailPage, albumsPage, currentID)

            createDir(currentID)

            saveLinktoFile(imgUrl, "./FacebookPhotos[{}_{}]/{}/{:04d}.jpg".format(start, end, currentID, getCurrentIndex4ID(currentID)))

            #del fullSize2thumbnail[imgUrl]
            #del thumbnailPage2albumPage
            q.task_done()
        except Exception:
            pass   
    pass   

def loadConfigs():
    global start
    global end 
    global fbUser
    global fbPassword
    global isProxyOpen
    try:
        inFile = open("configs.json", 'r')
    except:
        print("ERROR: configs.json is failed to be opened.")
        sys.exit(-1)

    jsonData = json.load(inFile)
    for key in jsonData:
        if key == 'start':
            start = jsonData[key]
        if key == 'end':
            end = jsonData[key]
        if key == "fbUser":
            fbUser = jsonData[key]
        if key == "fbPassword":
            fbPassword = jsonData[key]
        if key == "isProxyOpen":
            isProxyOpen = jsonData[key]

    inFile.close()

if __name__ == '__main__':

    print "===============start to load config file ==============="
    loadConfigs()

    #set proxy configuration
    if isProxyOpen:
        proxy = urllib2.ProxyHandler({'https': '127.0.0.1:1080'})
        opener = urllib2.build_opener(proxy)
        urllib2.install_opener(opener)

    for x in range(start, end):
        id2cnt[x] = 0
    #print getCurrentCounter()

    login2FBmobile()
    # for i in range(loginCNT):
    # 	worker = Thread(target=login2FBmobile, args=(i,))
    #     worker.setDaemon(True)
    #     worker.start()
    #     time.sleep(2)

    # Set up some threads to fetch the available albums for each user
    for i in range(num_albums_fetch):
        worker = Thread(target=accessAlbumPage, args=(i, id_queue,))
        #worker.setDaemon(True)
        worker.start()

    for i in range(num_thumbnail_fetch):
        worker = Thread(target=accessThumbnail, args=(i, albums_queue,))
        #worker.setDaemon(True)
        worker.start()
    
    for i in range(num_fullsize_fetch):
        worker = Thread(target=accessFullsize, args=(i, thumbnail_queue,))
        #worker.setDaemon(True)
        worker.start()

    for i in range(num_img_download):
        worker = Thread(target=downloadImage, args=(i, img_queue,))
        #worker.setDaemon(True)
        worker.start()            

    sleeptime = 1
    x = start
    #loop = 0
    while x < end:
        id_queue.put(x)
        x += 1
        #time.sleep(sleeptime)        

    id_queue.join()
    albums_queue.join()
    thumbnail_queue.join()
    img_queue.join()
