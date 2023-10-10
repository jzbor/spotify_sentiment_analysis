from typing import Optional
import requests
import matplotlib.pyplot as plt
from alive_progress import alive_bar

from dataclasses import dataclass
from datetime import datetime
from time import sleep
import argparse
import json
import sys

MIN_SECONDS: int = 10

global_id_cache: dict = {}
global_id_cache_hits: int = 0
global_data_cache: dict = {}
global_data_cache_hits: int = 0

@dataclass
class HistorySong:
    ms_played: int
    end_time: datetime
    artist_name: str
    track_name: str

    @staticmethod
    def from_dict(d: dict) -> "HistorySong":
        return HistorySong(
                ms_played=d['msPlayed'],
                end_time=datetime.strptime(d['endTime'], '%Y-%m-%d %H:%M'),
                artist_name=d['artistName'],
                track_name=d['trackName'],
                )

    def get_spotify_id(self, auth: dict, timeout: int = 30, cache: bool = False) -> str:
        if cache and (self.artist_name, self.track_name) in global_id_cache.keys():
            global global_id_cache_hits
            global_id_cache_hits += 1
            return global_id_cache[(self.artist_name, self.track_name)]

        response = requests.get('https://api.spotify.com/v1/search',
                                params={'q': f'{self.track_name}% {self.artist_name}', 'type': 'track', 'limit': 1},
                                headers={'Authorization': f'{auth["token_type"]}  {auth["access_token"]}'})

        if response.status_code == 429:
            if 'Retry-After' in response.headers.keys():
                timeout = int(response.headers['Retry-After'])
            eprint(f'Rate limit hit - sleeping for {timeout} seconds')
            sleep(timeout)
            return self.get_spotify_id(auth, timeout * 2, cache)
        else:
            try:
                items = json.loads(response.text)['tracks']['items']
                spotify_id = items[0]['id']
                if cache:
                    global_id_cache[(self.artist_name, self.track_name)] = spotify_id
                return spotify_id
            except Exception as e:
                eprint('Unexpected response:')
                eprint(response)
                die(f'Exception: ({e})')
                return ''  # just to make the linter happy; of course this won't get executed

    def get_audio_features(self, auth: dict, timeout: int = 30,
                           spotify_id: Optional[str] = None, cache: bool = False) -> dict:
        if spotify_id is None:
            spotify_id = self.get_spotify_id(auth, cache=cache)

        if cache and spotify_id in global_data_cache.keys():
            global global_data_cache_hits
            global_data_cache_hits += 1
            return global_data_cache[spotify_id]

        response = requests.get(f'https://api.spotify.com/v1/audio-features/{spotify_id}',
                                headers={'Authorization': f'{auth["token_type"]}  {auth["access_token"]}'})

        if response.status_code == 429:
            if 'Retry-After' in response.headers.keys():
                timeout = int(response.headers['Retry-After'])
            eprint(f'Rate limit hit - sleeping for {timeout} seconds')
            sleep(timeout)
            return self.get_audio_features(auth, timeout * 2, spotify_id)
        else:
            data = json.loads(response.text)
            if cache:
                global_data_cache[spotify_id] = data
            return data


@dataclass
class DataSong(HistorySong):
    spotify_id: str
    data: dict

    def to_dict(self) -> dict:
        d = self.__dict__
        d['end_time'] = self.end_time.strftime('%Y-%m-%d %H:%M')
        return d

    @staticmethod
    def from_dict(d: dict) -> "DataSong":
        return DataSong(
                ms_played=d['ms_played'],
                end_time=datetime.strptime(d['end_time'], '%Y-%m-%d %H:%M'),
                artist_name=d['artist_name'],
                track_name=d['track_name'],
                spotify_id = d['spotify_id'],
                data = d['data'],
                )

    @staticmethod
    def from_history_song(s: HistorySong, auth: dict, cache: bool = False) -> "DataSong":
        spotify_id=s.get_spotify_id(auth, cache=cache)
        return DataSong(
                ms_played=s.ms_played,
                end_time=s.end_time,
                artist_name=s.artist_name,
                track_name=s.track_name,
                spotify_id=spotify_id,
                data=s.get_audio_features(auth, spotify_id=spotify_id, cache=cache)
                )


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def die(msg: str):
    eprint(msg)
    sys.exit(1)


def get_spotify_access_token(args) -> dict:
    if args.client_id:
        client_id = args.client_id
    else:
        with open('./client_id', 'r') as file:
            client_id = file.read().strip()

    if args.client_secret:
        client_secret = args.client_secret
    else:
        with open('./client_secret', 'r') as file:
            client_secret = file.read().strip()

    request_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            }
    response = requests.post('https://accounts.spotify.com/api/token',
                             headers={'Content-Type': 'application/x-www-form-urlencoded'},
                             data=request_data)
    return json.loads(response.text)


def read_hist_file(path: str, args) -> list[HistorySong]:
    with open(path, 'r') as file:
        parsed = json.load(file)
        history = [HistorySong.from_dict(d) for d in parsed]

        # filter songs
        if args.min_duration:
            history = [song for song in history if song.ms_played >= args.min_duration * 1000]

        # apply offset
        if args.offset:
            history = history[args.offset:]

        # apply size restriction
        if args.nsongs:
            history = history[:args.nsongs]

        return history


def read_data_file(path: str, args) -> list[DataSong]:
    with open(path, 'r') as file:
        parsed = json.load(file)
        dataset = [DataSong.from_dict(d) for d in parsed]

        # filter songs
        if args.min_duration:
            dataset = [song for song in dataset if song.ms_played >= args.min_duration * 1000]

        # apply offset
        if args.offset:
            dataset = dataset[args.offset:]

        # apply size restriction
        if args.nsongs:
            dataset = dataset[:args.nsongs]

        return dataset


def gen_data(args):
    if not args.hist_file:
        die('No history file provided (-f)')
    if not args.data_file:
        die('No data file provided (-d)')

    eprint('=> Reading history file')
    history = read_hist_file(args.hist_file, args)

    eprint('=> Fetching Spotify API authorization')
    auth = get_spotify_access_token(args)

    eprint('=> Fetching data')
    dataset = []
    with alive_bar(len(history)) as bar:
        for song in history:
            dataset.append(DataSong.from_history_song(song, auth, cache=args.cache))
            bar()
    if args.cache:
        eprint(f'Id cache hits: {global_id_cache_hits} ({global_id_cache_hits/len(history) * 100 :.1f}%)')
        eprint(f'Data cache hits: {global_data_cache_hits} ({global_data_cache_hits/len(history) * 100 :.1f}%)')

    eprint('=> Exporting data')
    with open(args.data_file, 'w') as file:
        dict_data = [song.to_dict() for song in dataset]
        json.dump(dict_data, file, ensure_ascii=False, indent=4)


def visualize(args):
    if not args.data_file:
        die('No data file provided (-d)')

    eprint('=> Reading data file')
    dataset = read_data_file(args.data_file, args)

    if args.by_day:
        eprint('=> Accumulating data by day')
        days = {}
        for song in dataset:
            if song.end_time.date() not in days.keys():
                days[song.end_time.date()] = []
            days[song.end_time.date()].append(song.data[args.parameter])
        xvalues = [k for k in days]
        yvalues = [sum(days[k]) / len(days[k]) for k in days]
    else:
        xvalues = [song.end_time for song in dataset]
        yvalues = [song.data[args.parameter] for song in dataset]

    eprint('=> Creating plot')
    plt.plot(xvalues, yvalues)
    plt.xlabel('date')
    plt.ylabel(args.parameter)
    plt.savefig(args.plot_file)


def visualize_time(args):
    if not args.data_file:
        die('No data file provided (-d)')

    eprint('=> Reading data file')
    dataset = read_data_file(args.data_file, args)

    eprint('=> Accumulating data by day')
    days = {}
    for song in dataset:
        if song.end_time.date() not in days.keys():
            days[song.end_time.date()] = []
        days[song.end_time.date()].append(song.ms_played / 1000 / 60)  # convert to minutes

    eprint('=> Creating plot')
    plt.plot([k for k in days], [len(days[k]) for k in days])
    plt.plot([k for k in days], [sum(days[k]) for k in days])
    plt.xlabel('date')
    plt.ylabel('songs played (blue) / minutes listened (yellow)')
    plt.savefig(args.plot_file)


def parse_args():
    cli = argparse.ArgumentParser(description='Performing sentiment analysis on Spotify playback history')
    cli.add_argument('-i', '--client-id', help='Spotify API client id (otherwise read from ./client_id)', type=str)
    cli.add_argument('-s', '--client-secret',
                     help='Spotify API client secret (otherwise read from ./client_secret)', type=str)
    cli.add_argument('-c', '--cache', help='cache Spotify API calls', action='store_true')
    cli.add_argument('-f', '--hist-file', help='history file', type=str)
    cli.add_argument('-d', '--data-file', help='data file', type=str)
    cli.add_argument('-p', '--plot-file', help='plot file', type=str, default='plot.png')
    cli.add_argument('-o', '--offset', help='offset song data', type=int)
    cli.add_argument('-n', '--nsongs', help='limit number of songs to be processed', type=int)
    cli.add_argument('-m', '--min-duration',
                     help='filter any songs that have been played shorter than n seconds', type=int)
    subparsers = cli.add_subparsers(required=True)

    cli_gen_data = subparsers.add_parser('gen-data', help='generate data by fetching metadata from Spotify')
    cli_gen_data.set_defaults(func=gen_data)

    cli_visualize = subparsers.add_parser('visualize', help='visualize metadata as provided by spotify')
    cli_visualize.add_argument('parameter', help='data parameter to visualize', type=str)
    cli_visualize.add_argument('--by-day', help='group data by days', action='store_true')
    cli_visualize.set_defaults(func=visualize)

    cli_visualize_time = subparsers.add_parser('visualize-time',
                                               help='visualize total number songs and minutes played per day')
    cli_visualize_time.set_defaults(func=visualize_time)

    return cli.parse_args()


if __name__ == '__main__':
    args = parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        die('Interrupted')
