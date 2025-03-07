import asyncio
import aiohttp
import json
import argparse
import ssl
import openai
from groq import Groq
import itertools
from itertools import islice
from urllib.parse import urlparse

# Async function to handle Gemini requests
async def gemini_request(text):
    global config
    api_key = config.get("GEMINI_API_KEY")

    if not api_key:
        print("[!] Could not detect Gemini API key")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": text}]}]}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                return parse_gemini_response(await response.json())
            else:
                print(f"[!] Gemini Error: {response.status}")
                return None


# Async function to handle DeepSeek requests
async def deepseek_request(text):
    global config
    client = openai.AsyncOpenAI(api_key=config.get("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
    if not client:
        print("[!] Could not detect OpenRouter API key.")
        return None

    response = await client.chat.completions.create(
        model="deepseek/deepseek-r1:free",
        messages=[{"role": "user", "content": text}]
    )

    return parse_deepseek_response(response)

# Async function to handle Groq requests
async def groq_request(text):
    global config
    api_key = config.get("GROQ_API_KEY")
    if not api_key:
        print("[!] Could not detect Groq API key")
        return None
    print(f"[+] Making Groq API call")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": f"{text}",
        }
    ],
    model="llama-3.3-70b-versatile",
    )
    return parse_groq_response(response)

# Parse responses from the APIs
def parse_gemini_response(response):
    return [x for x in response["candidates"][0]["content"]["parts"][0]["text"].split('\n') if x]

def parse_deepseek_response(response):
    return response.choices[0].message.content.split("\n")

def parse_groq_response(response):
    return response.choices[0].message.content.split("\n")

# Write results to file
def write_subs(outfile, response_text):
    with open(outfile, 'a') as out_fd:
        for line in response_text:
            out_fd.write(f"{line}\n")

# Round-robin API selection
async def generate_requests(domains, prompt, outfile, batch_size, disable_ssl):
    tasks = []
    api_functions = itertools.cycle([gemini_request, deepseek_request, groq_request])
    for batch in batch_iterable(domains, batch_size):
        batch_text = "<".join(batch)
        request_func = next(api_functions)
        tasks.append(asyncio.create_task(handle_batch(batch_text, prompt, outfile, request_func)))
    await asyncio.gather(*tasks)

# Handle a batch request
async def handle_batch(batch_text, prompt, outfile, request_func):
    response = await request_func(f"{prompt} {batch_text}")
    if response and outfile:
        write_subs(outfile, response)
    print("[!] Generated entries:")
    for r in response:
        print(r)

# Batch iterable
def batch_iterable(iterable, batch_size):
    iterator = iter(iterable)
    while batch := list(islice(iterator, batch_size)):
        yield batch

# Load config
def load_config(config_file):
    with open(config_file, 'r') as file:
        return json.load(file)

# Read domains from input file
def read_domains(input_file):
    with open(input_file, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]

# Main function
def main():
    global config
    parser = argparse.ArgumentParser(description="Make API requests using domains and API keys from config file.")
    parser.add_argument("-d", "--directory_mode", action="store_true", help="Generate directories instead of subdomains.")
    parser.add_argument("-s", "--domain_mode", action="store_true", help="Generate subdomains instead of directories.")
    parser.add_argument("-f", "--input_file", required=True, help="File containing a list of domains.")
    parser.add_argument("-c", "--config_file", required=True, help="JSON config file with API keys.")
    parser.add_argument("-p", "--prompt", help="Custom prompt for subdomain/directory generation.")
    parser.add_argument("-b", "--batch_size", type=int, default=100, help="Batch request size. Default is 100.")
    parser.add_argument("-o", "--output", help="Write results to a file.")
    parser.add_argument("--disable_ssl", action="store_true", help="Disable SSL verification for requests.")
    args = parser.parse_args()

    config = load_config(args.config_file)

    if args.prompt:
        prompt = args.prompt
    elif args.domain_mode:
        prompt = "There are {batch_size} subdomains separated by a < character. Based on the sample subdomains, generate 150 new possible subdomains. Only return the subdomains. Do not number them."
    elif args.directory_mode:
        prompt = "There are {batch_size} URLs separated by a < character. Based on the sample URLS and folders, generate 150 new possible directory paths. Only return the directory paths. Do not number them or place any formatting."
    
    entries = read_domains(args.input_file)
    asyncio.run(generate_requests(entries, prompt, args.output, args.batch_size, args.disable_ssl))

if __name__ == "__main__":
    main()
