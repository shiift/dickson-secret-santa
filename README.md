Secret Santa Generator

Participants file should look like the following:

`First Name, Family Name (Used to separate families)`

```
Liam, Li Dickson
Eileen, Li Dickson
Tim, Tim Dickson
Lydia, Tim Dickson
Chris, Chris Dickson
Rob, Song Dickson
Kyoung-Hi, Song Dickson
Mina, Song Dickson
Carol, Deasy Dickson
Kim, Deasy Dickson
Jeff, Klotzkin Dickson
Jeanine, Klotzkin Dickson
Eliza, Klotzkin Dickson
Kyle, Klotzkin Dickson
```

Run the script with

`python3 dickson_secret_santa file.txt`

```
usage: dickson_secret_santa [-h] [-f] [-r] file

Generates a list of people pairings for a secret santa exchange.

positional arguments:
  file                  path to the csv containing a list of people for the
                        exchange

optional arguments:
  -h, --help            show this help message and exit
  -f, --no-family-match
                        do not match families for the exchange (uses surname)
  -r, --no-reversals    do not match people to each other
```