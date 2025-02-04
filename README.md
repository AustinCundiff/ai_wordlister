# AI_Wordlister
Queries Free AI Services in order to build word lists for content discovery & fuzzing.

### Usage:
usage: ai_wordlister.py [-h] [-d] -f DOMAIN_FILE -c CONFIG_FILE [-p PROMPT] [-o OUTPUT]

Make API requests using domains and API keys from config file.

options:
  -h, --help            show this help message and exit
  -d, --domain_mode     Generate subdomains instead of directories. (Default= yes)
  -f DOMAIN_FILE, --domain_file DOMAIN_FILE
                        File containing a list of domains.
  -c CONFIG_FILE, --config_file CONFIG_FILE
                        JSON config file with API keys.
  -p PROMPT, --prompt PROMPT
                        E.g. Subdomains separated by a colon. Use this list as a seed, generate X new subdomains. Only return subdomains for DOMAIN.
  -o OUTPUT, --output OUTPUT
                        Write subdomains to a file.

