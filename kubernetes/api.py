#!/usr/bin/env python
#
# Copyright 2014 tigmi
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''A library that provides a Python interface to the Kubernetes API'''

import sys
import urllib
import urllib2
import urlparse
import requests

import urllib3
#urllib3.disable_warnings()

from kubernetes import (__version__,
                        _FileCache,
                        simplejson,
                        KubernetesError,
                        PodList,
                        ReplicationControllerList,
                        ServiceList,
                        ReplicationController,
                        Pod,
                        Service)

# A singleton representing a lazily instantiated FileCache.
DEFAULT_CACHE = object()

class Api(object):
    '''A python interface into the Kubernetes API'''
    def __init__(self,
                user_id=None,
                user_password=None,
                input_encoding=None,
                request_headers=None,
                cache=DEFAULT_CACHE,
                base_url=None,
                debugHTTP=None,
                timeout=None):
        '''Instantiate a new kubernetes.Api object

        Args:
          user_id:
            Your agent user id
          user_password
            Your agent user password
          input_encoding:
              The encoding used to encode input strings. [Optional]
          request_headers
              A dictionary of additional HTTP request headers. [Optional]
          cache:
              The cache instance to use. Defaults to DEFAULT_CACHE.
              Use None to disable caching. [Optional]
          base_url:
            The base URL to use to contact the kubernetes API.
            Defaults to https://10.245.1.2/api/v1beta2
          debugHTTP:
              Set to True to enable debug output from urllib2 when performing
            any HTTP requests.  Defaults to False. [Optional]
          timeout:
            Set timeout (in seconds) of the http/https requests. If None the
            requests lib default will be used.  Defaults to None. [Optional]
        '''
        self.SetCache(cache)
        self._urllib    =    urllib2
        self._input_encoding = input_encoding
        self._debugHTTP    =    debugHTTP
        self._timeout    =    timeout

        self._InitializeRequestHeaders(request_headers)
        self._InitializeUserAgent()
        self._InitializeDefaultParameters()

        if base_url is None:
            self.base_url = 'https://10.245.1.2/api/v1beta2'
        else:
            self.base_url = base_url

        #if user_id is None or user_password is None:
            #print >> sys.stderr, 'Kubernetes requires user_id, user_password.'

            #raise KubernetesError({'message': "Kubernetes requires user_id and user_password"})

        #self.SetCredentials(user_id, user_password)

        if debugHTTP:
            import logging
            import httplib
            httplib.HTTPConnection.debuglevel = 1

            logging.basicConfig()
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True

    def SetCredentials(self,
        user_id,
        user_password):
        '''Set the user_id and user_password for this instance

        Args:
          user_id:
              Your agent user id
          user_password:
              Your agent user password
        '''
        self._user_id = user_id
        self._user_password = user_password

        auth_list = [user_id, user_password]
        if all(auth_list):
            self.__auth = (user_id, user_password)

        self._config = None

    def ClearCredentials(self):
        '''Clear any credentials for this instance'''
        self._user_id = None
        self._user_password = None

    def DeleteService(self, name, namespace='default'):
        '''Delete a new Service'''

        url = ('%(base_url)s/namespaces/%(ns)s/services/%(name)s' %
               {"base_url":self.base_url, "ns":namespace, "name":name})
        json = self._RequestUrl(url, 'DELETE')
        if json.status_code not in [200, 404]:
            raise KubernetesError({'message': 'parsing error ['+simplejson.dumps(json.content)+']'})

    def DeletePods(self, name, namespace='default'):
        '''Delete a new Pod'''

        url = ('%(base_url)s/namespaces/%(ns)s/pods/%(name)s' %
               {"base_url":self.base_url, "ns":namespace, "name":name})
        json = self._RequestUrl(url, 'DELETE')
        if json.status_code not in [200, 404]:
            raise KubernetesError({'message': 'parsing error ['+simplejson.dumps(json.content)+']'})

    def DeleteReplicationController(self, name, namespace='default'):
        '''Delete a new Service'''

        url = ('%(base_url)s/namespaces/%(ns)s/replicationcontrollers/%(name)s' %
               {"base_url":self.base_url, "ns":namespace, "name":name})
        json = self._RequestUrl(url, 'DELETE')
        if json.status_code not in [200, 404]:
            raise KubernetesError({'message': 'parsing error ['+simplejson.dumps(json.content)+']'})

    def CreateService(self, data, namespace='default'):
        '''Create a new Service'''

        url = ('%(base_url)s/namespaces/%(ns)s/services' %
               {"base_url":self.base_url, "ns":namespace})
        json = self._RequestUrl(url, 'POST', data)
        if json.status_code is not 201:
            raise KubernetesError({'message': 'parsing error ['+simplejson.dumps(json.content)+']'})
        result = self._ParseAndCheckKubernetes(json.content)
        return Service.NewFromJsonDict(result)

    def CreateReplicationController(self, data, namespace='default'):
        '''Create a new ReplicationController'''

        url = ('%(base_url)s/namespaces/%(ns)s/replicationcontrollers' %
               {"base_url":self.base_url, "ns":namespace})
        json = self._RequestUrl(url, 'POST', data)
        if json.status_code is not 201:
            raise KubernetesError({'message': 'parsing error ['+simplejson.dumps(json.content)+']'})
        result = self._ParseAndCheckKubernetes(json.content)
        return ReplicationController.NewFromJsonDict(result)

    def CreatePod(self, data, namespace='default'):
        '''Create a new Pod'''

        url = ('%(base_url)s/namespaces/%(ns)s/pods' %
               {"base_url":self.base_url, "ns":namespace})
        json = self._RequestUrl(url, 'PUT', data)
        if json.status_code is not 201:
            raise KubernetesError({'message': 'parsing error ['+simplejson.dumps(json.content)+']'})
        result = self._ParseAndCheckKubernetes(json.content)
        return Pod.NewFromJsonDict(result)

    def GetPod(self, name, namespace='default'):
        '''List the specific pod on this cluster'''

        # Make and send requests
        url = ('%(base_url)s/namespaces/%(ns)s/pods/%(name)s' %
               {"base_url":self.base_url, "ns":namespace, "name":name})
        json = self._RequestUrl(url, 'GET')
        if json.status_code == 404:
            #not exit, just return None
            return None
        data = self._ParseAndCheckKubernetes(json.content)
        return Pod.NewFromJsonDict(data)

    def GetPods(self, namespace=None, selector=None):
        '''List all pods on this cluster'''

        # Make and send requests
        if namespace:
            url = ('%(base_url)s/namespaces/%(ns)s/pods' %
                {"base_url":self.base_url, "ns":namespace})
        else:
            url = '%s/pods' % self.base_url
        if selector:
            selector_str = 'name=%s' % selector
            #TODO selector name would be replaced by 'labelSelector' soon
            url = self._BuildUrl(url, extra_params={'label-selector':selector_str})
        json = self._RequestUrl(url, 'GET')
        data = self._ParseAndCheckKubernetes(json.content)
        return PodList.NewFromJsonDict(data)

    def _HandleReplicationController(self, name, namespace, action, data_str=None):
        '''Retrieve the specific ReplicationController and convert to dict'''
        # Make and send requests
        url = ('%(base_url)s/namespaces/%(ns)s/replicationcontrollers/%(name)s' %
               {"base_url":self.base_url, "ns":namespace, "name":name})
        json = self._RequestUrl(url, action, data_str)
        return json

    def ResizeReplicationController(self, name, replicas, namespace='default'):
        '''Update an existing ReplicationController by given data'''
        #retrieve the specific replicationcontroller first
        json = self._HandleReplicationController(name=name,
                                                 action='GET',
                                                 namespace=namespace)
        if json.status_code == 404:
            #not exit, just return None
            return None
        data = self._ParseAndCheckKubernetes(json.content)
        #update the value of replicas, note, for v1beta3 only
        data['spec']['replicas']=replicas
        json = self._HandleReplicationController(name=name,
                                                 action='PUT',
                                                 namespace=namespace,
                                                 data_str=simplejson.dumps(data))
        if json.status_code is not 200:
            raise KubernetesError({'message': 'parsing error ['+simplejson.dumps(json.content)+']'})
        result = self._ParseAndCheckKubernetes(json.content)
        return ReplicationController.NewFromJsonDict(result)

    def GetReplicationController(self, name, namespace='default'):
        '''Retrieve the specific replicationcontroller on this cluster'''
        json = self._HandleReplicationController(name=name,
                                                       action='GET',
                                                       namespace=namespace)
        if json.status_code == 404:
            #not exit, just return None
            return None
        data = self._ParseAndCheckKubernetes(json.content)
        return ReplicationController.NewFromJsonDict(data)

    def GetReplicationControllers(self, namespace=None):
        '''List all replicationcontrollers on this cluster'''
        # Make and send requests
        if namespace:
            url = ('%(base_url)s/namespaces/%(ns)s/replicationcontrollers' %
                {"base_url":self.base_url, "ns":namespace})
        else:
            url = '%s/replicationcontrollers' % self.base_url
        json = self._RequestUrl(url, 'GET')
        data = self._ParseAndCheckKubernetes(json.content)
        return ReplicationControllerList.NewFromJsonDict(data)

    def GetService(self, name, namespace='default'):
        '''List the specific service on this cluster'''

        # Make and send requests
        url = ('%(base_url)s/namespaces/%(ns)s/services/%(name)s' %
               {"base_url":self.base_url, "ns":namespace, "name":name})
        json = self._RequestUrl(url, 'GET')
        if json.status_code == 404:
            #not exit, just return None
            return None
        data = self._ParseAndCheckKubernetes(json.content)
        return Service.NewFromJsonDict(data)

    def GetServices(self, namespace=None):
        '''List all services on this cluster'''

        # Make and send requests
        if namespace:
            url = ('%(base_url)s/namespaces/%(ns)s/services' %
                {"base_url":self.base_url, "ns":namespace})
        else:
            url = '%s/services' % self.base_url
        json = self._RequestUrl(url, 'GET')
        data = self._ParseAndCheckKubernetes(json.content)
        return ServiceList.NewFromJsonDict(data)

    def SetCache(self, cache):
        '''Override the default cache.  Set to None to prevent caching.

        Args:
          cache:
            An instance that supports the same API as the kubernetes._FileCache
        '''
        if cache == DEFAULT_CACHE:
            self._cache = _FileCache()
        else:
            self._cache = cache

    def _InitializeRequestHeaders(self, request_headers):
        if request_headers:
            self._request_headers = request_headers
        else:
            self._request_headers = {}

    def _InitializeUserAgent(self):
        user_agent = 'Python-urllib/%s (python-kubernetes/%s)' % \
            (self._urllib.__version__, __version__)
        self.SetUserAgent(user_agent)

    def _InitializeDefaultParameters(self):
        self._default_params = {}

    def SetUserAgent(self, user_agent):
        '''Override the default user agent.

        Args:
          user_agent:
              A string that should be send to the server as the user-agent.
        '''
        self._request_headers['User-Agent'] = user_agent

    def _Encode(self, s):
        if self._input_encoding:
            return unicode(s, self._input_encoding).encode('utf-8')
        else:
            return unicode(s).encode('utf-8')

    def _EncodeParameters(self, parameters):
        '''Return a string in key=value&key=value form

        Value of None are not included in the output string.

        Args:
         parameters:
             A dict of (key, value) tuples, where value is encoded as
             specified by self._encoding

        Returns:
         A URL-encoded string in "key=value&key=value" form
        '''
        if parameters is None:
            return None
        else:
            return urllib.urlencode(dict([(k, self._Encode(v)) for k, v in parameters.items() if v is not None]))


    def _BuildUrl(self, url, path_elements=None, extra_params=None):
        # Break url into constituent parts
        (scheme, netloc, path, params, query, fragment) = urlparse.urlparse(url)

        # Add any additional path elements to the path
        if path_elements:
            # Filter out the path elements that have a value of None
            p = [i for i in path_elements if i]
            if not path.endswith('/'):
                path += '/'
            path += '/'.join(p)

        # add any additional query parameters to the query string
        if extra_params and len(extra_params) > 0:
            extra_query = self._EncodeParameters(extra_params)
            # Add it to the existing query
            if query:
                query += '&' + extra_query
            else:
                query = extra_query

        # Return the rebuilt URL
        return urlparse.urlunparse((scheme, netloc, path, params, query, fragment))

    def _RequestUrl(self, url, verb, data=None):
        '''Request a url.

            Args:
             url:
                 The web location we want to retrieve.
             verb:
                 POST, GET, PUT, DELETE.
             data:
                 a dict of (str, unicode) key/value pairs.

            Returns:
             A JSON object.
        '''
        if verb == 'POST':
            try:
                return requests.post(
                    url,
                    data=data,
                    auth=None,
                    timeout=self._timeout,
                    verify=False
                    )
            except requests.RequestException as e:
                raise KubernetesError(str(e))
        if verb == 'GET':
            try:
                return requests.get(
                    url,
                    auth=None,
                    timeout=self._timeout,
                    verify=False
                    )
            except requests.RequestException as e:
                raise KubernetesError(str(e))
        if verb == 'PUT':
            try:
                return requests.put(
                    url,
                    data=data,
                    auth=None,
                    timeout=self._timeout,
                    verify=False
                    )
            except requests.RequestException as e:
                raise KubernetesError(str(e))
        if verb == 'DELETE':
            try:
                return requests.delete(
                    url,
                    auth=None,
                    timeout=self._timeout,
                    verify=False
                    )
            except requests.RequestException as e:
                raise KubernetesError(str(e))
        return 0

    def _ParseAndCheckKubernetes(self, json):
        '''Try and parse the JSON returned from Kubernetes and return
        an empty dictionary if there is any error
        '''

        try:
            data = simplejson.loads(json)
        except ValueError:
            raise KubernetesError({'message': 'parsing error ['+json+']'})

        return data
