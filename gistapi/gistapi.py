# coding=utf-8
"""
Exposes a simple HTTP API to search a users Gists via a regular expression.

Github provides the Gist service as a pastebin analog for sharing code and
other develpment artifacts.  See http://gist.github.com for details.  This
module implements a Flask server exposing two endpoints: a simple ping
endpoint to verify the server is up and responding and a search endpoint
providing a search across all public Gists for a given Github account.
"""

import re
from typing import Tuple
import requests
from flask import Flask, jsonify, request
import requests_cache

# *The* app object
app = Flask(__name__)

requests_cache.install_cache(cache_name='gist_app_cache', expire_after=300)


@app.route("/ping")
def ping():
    """Provide a static response to a simple GET request."""
    return "pong"


def gists_for_user(username) -> Tuple[bool, str, dict]:
    """Provides the list of gist metadata for a given user.

    This abstracts the /users/:username/gist endpoint from the Github API.
    See https://developer.github.com/v3/gists/#list-a-users-gists for
    more information.

    Args:
        username (string): the user to query gists for

    Returns:
        The dict parsed from the json response from the Github API.  See
        the above URL for details of the expected structure.
    """
    gists_url = 'https://api.github.com/users/{username}/gists'.format(
        username=username)
    # we might want to disable cache for this request
    # with requests_cache.disabled():
    response = requests.get(gists_url)
    # BONUS: What failures could happen?
    # BONUS: Paging? How does this work for users with tons of gists?
    json_data = response.json()
    if response.status_code == 200:
        return True, "Successful", json_data
    return False, json_data['message'], json_data


@app.route("/api/v1/search", methods=['POST'])
def search():
    """Provides matches for a single pattern across a single users gists.

    Pulls down a list of all gists for a given user and then searches
    each gist for a given regular expression.

    Returns:
        A Flask Response object of type application/json.  The result
        object contains the list of matches along with a 'status' key
        indicating any failure conditions.
    """
    post_data = request.get_json()
    if post_data:
        # BONUS: Validate the arguments?
        if 'username' not in post_data:
            return jsonify({'status': 'failed', 'message': 'username is required'})

        if 'pattern' not in post_data:
            return jsonify({'status': 'failed', 'message': 'pattern is required'})

        username = post_data['username']
        pattern = post_data['pattern']

        result = {}
        # BONUS: Handle invalid users?
        is_successful, msg, data = gists_for_user(username)
        if is_successful:
            match_list = []
            regex_pattern = re.compile(pattern, re.MULTILINE | re.IGNORECASE)
            for gist in set(data):
                # REQUIRED: Fetch each gist and check for the pattern
                # BONUS: What about huge gists?
                # BONUS: Can we cache results in a datastore/db?
                # _, value = gist['files'].popitem()
                value, = gist['files'].values()
                raw_url = value['raw_url']
                response = requests.get(raw_url)
                if response.status_code == 200:
                    matches = regex_pattern.findall(response.text)
                    if len(matches) > 0:
                        match_list.append(
                            f"https://gist.github.com/{username}/{gist['id']}")

            result['status'] = 'success'
            result['username'] = username
            result['pattern'] = pattern
            result['matches'] = match_list
        else:
            result['status'] = 'failed'
            result['message'] = msg
            result['username'] = username
            result['pattern'] = pattern
            result['matches'] = []

        return jsonify(result)
    else:
        return jsonify({'status': 'failed', 'message': 'Invalid parameters'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9876)
