# AI_Wordlister
Queries Free AI Services in a round-robin fashion to build word lists for content discovery & fuzzing. It currently supports Deepseek, Gemini, and Groq.

### Install
```
go build -o aiwordlister aiwordlister.go
```

Ensure you obtain API keys for Groq, Openrouter, and Gemini and place them in your config.ini file. An example is included in this repository. Beaware that you may hit rate limits.
### Usage:
```
options:
  -h, --help            show this help message and exit
  -d, --directory_mode  Generate directories instead of subdomains based on a list of URLs
  -s, --domain_mode     Generate subdomains instead of directories. (Default= yes)
  -f INPUT_FILE, --input_file INPUT_FILE
                        File containing a list of domains.
  -c CONFIG_FILE, --config_file CONFIG_FILE
                        JSON config file with API keys.
  -p PROMPT, --prompt PROMPT
                        E.g. Subdomains separated by a <. Use this list as a seed, generate X new subdomains. Only return subdomains for DOMAIN.
  -b BATCH_SIZE, --batch_size BATCH_SIZE
                        Batched request size. Default is 100.
  -o OUTPUT, --output OUTPUT
                        Write subdomains to a file.

```
## Example
```bash
# Generate directories using URLs in a file named urls.txt and output to a file called output_test.txt.
aiwordlister -c config -f urls.txt -d -o output_test.txt
# Generate subdomains using a file of domains:
aiwordlister  -c config -f domains.txt -s -o output_test.txt
```
