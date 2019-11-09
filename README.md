Secret Santa Generator

Participants file should look like the following:

`First Name, Family Name (Used to separate families), Phone Number (optional)`

```
Liam, Li Dickson, 15555555
Eileen, Li Dickson, 15555555
Tim, Tim Dickson, 15555555
Lydia, Tim Dickson, 15555555
Chris, Chris Dickson, 15555555
Rob, Song Dickson, 15555555
Kyoung-Hi, Song Dickson, 15555555
Mina, Song Dickson, 15555555
Carol, Deasy Dickson, 15555555
Kim, Deasy Dickson, 15555555
Jeff, Klotzkin Dickson, 15555555
Jeanine, Klotzkin Dickson, 15555555
Eliza, Klotzkin Dickson, 15555555
Kyle, Klotzkin Dickson, 15555555
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