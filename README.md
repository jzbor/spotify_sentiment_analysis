# Spotify Sentiment Analysis
This is a small tool to help with sentiment analysis on Spotify listening histories.
It history data, which can be requested by the users in combination with metadata provided by the [Spotify Web API](https://developer.spotify.com/documentation/web-api).

## Installation
1. First you need to install Python 3 (tested with 3.10) and poetry
2. Then you can fetch the dependencies with `poetry install`
3. You should now be able to run the script through `poetry`:
	```sh
	poetry run python3 ./spot_analyze.py -h
	```

## Usage
This program consists of two stages:
1. data gathering - access to the [Spotify Web API](https://developer.spotify.com/documentation/web-api) is required
2. data processing/visualization - the data gathered in step 1 can be visualized in various ways

### Data Gathering
1. You need to set up a Spotify Developer account and create an App as described [here](https://developer.spotify.com/documentation/web-api/tutorials/getting-started).
2. Then you can get the Client ID and Client Secret for your App from the Developer Dashboard.
3. Put these into the files `./client_id` and `./client_secret` respectively.
4. Get your history file (should be a `.json` file) and store it somewhere in the current directory.
5. Now you are ready to generate your first data:
	```sh
	poetry run python3 ./spot_analyze.py --hist-file StreamingHistory0.json --data-file data.json --nsongs 10 gen-data
	```
6. To minimize usage of the Spotify API and avoid rate limiting the following parameters might be helpful:
	* `-c, --cache` - this lets the script cache calls to the Spotify API and therefore avoids unnecessary calls for information we already have
	* `-m N, --min-duration N` - filters out songs that have been played shorter than `N` seconds.
	* `-n N, --nsongs` - limit the number of songs to be processed
	* `-h, --help` - find out about more options
	So we get:
	```sh
	poetry run python3 ./spot_analyze.py -h StreamingHistory0.json -d data.json -m 10 -n 200 gen-data
	```

*Please note that data provided by Spotify may not be used to train AI models!*

### Data Visualization
You can generate diagrams for all metrics listed [here](https://developer.spotify.com/documentation/web-api/reference/get-audio-features):
```sh
poetry run python3 spot_analyze.py -d data.json visualize valence
```
There is also the possibility to use the average value per day:
```sh
poetry run python3 spot_analyze.py -d data.json visualize valence --by-day
```
And you can visualize the total number of tracks and minutes listened (also grouped by day):
```
poetry run python3 spot_analyze.py -d data.json visualize-time
```


