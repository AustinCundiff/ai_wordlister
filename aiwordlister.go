package main

import (
    "bufio"
    "bytes"
    "context"
    "crypto/tls"
    "encoding/json"
    "flag"
    "fmt"
//    "io"
    "net/http"
    "os"
    "strings"
    "sync"
    "sync/atomic"
    "time"
)

type Config struct {
    GeminiAPIKey     string `json:"GEMINI_API_KEY"`
    OpenRouterAPIKey string `json:"OPENROUTER_API_KEY"`
    GroqAPIKey       string `json:"GROQ_API_KEY"`
}

type apiFunc func(string, *Config, *http.Client) ([]string, error)

func geminiRequest(text string, cfg *Config, client *http.Client) ([]string, error) {
    if cfg.GeminiAPIKey == "" {
        return nil, fmt.Errorf("missing Gemini API key")
    }
    url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=%s", cfg.GeminiAPIKey)
    payload := map[string]interface{}{
        "contents": []map[string]interface{}{
            {"parts": []map[string]string{{"text": text}}},
        },
    }
    body, _ := json.Marshal(payload)
    resp, err := client.Post(url, "application/json", bytes.NewReader(body))
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("gemini error: %s", resp.Status)
    }
    var parsed struct {
        Candidates []struct {
            Content struct {
                Parts []struct {
                    Text string `json:"text"`
                } `json:"parts"`
            } `json:"content"`
        } `json:"candidates"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
        return nil, err
    }
    if len(parsed.Candidates) == 0 || len(parsed.Candidates[0].Content.Parts) == 0 {
        return nil, fmt.Errorf("unexpected gemini response")
    }
    lines := strings.Split(parsed.Candidates[0].Content.Parts[0].Text, "\n")
    return filterEmpty(lines), nil
}

func deepseekRequest(text string, cfg *Config, client *http.Client) ([]string, error) {
    if cfg.OpenRouterAPIKey == "" {
        return nil, fmt.Errorf("missing OpenRouter API key")
    }
    url := "https://openrouter.ai/api/v1/chat/completions"
    payload := map[string]interface{}{
        "model": "deepseek/deepseek-r1:free",
        "messages": []map[string]string{
            {"role": "user", "content": text},
        },
    }
    body, _ := json.Marshal(payload)
    req, _ := http.NewRequest("POST", url, bytes.NewReader(body))
    req.Header.Set("Authorization", "Bearer "+cfg.OpenRouterAPIKey)
    req.Header.Set("Content-Type", "application/json")
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("deepseek error: %s", resp.Status)
    }
    var parsed struct {
        Choices []struct {
            Message struct {
                Content string `json:"content"`
            } `json:"message"`
        } `json:"choices"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
        return nil, err
    }
    if len(parsed.Choices) == 0 {
        return nil, fmt.Errorf("unexpected deepseek response")
    }
    lines := strings.Split(parsed.Choices[0].Message.Content, "\n")
    return filterEmpty(lines), nil
}

func groqRequest(text string, cfg *Config, client *http.Client) ([]string, error) {
    if cfg.GroqAPIKey == "" {
        return nil, fmt.Errorf("missing Groq API key")
    }
    url := "https://api.groq.com/openai/v1/chat/completions"
    payload := map[string]interface{}{
        "model": "llama-3.3-70b-versatile",
        "messages": []map[string]string{
            {"role": "user", "content": text},
        },
    }
    body, _ := json.Marshal(payload)
    req, _ := http.NewRequest("POST", url, bytes.NewReader(body))
    req.Header.Set("Authorization", "Bearer "+cfg.GroqAPIKey)
    req.Header.Set("Content-Type", "application/json")
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("groq error: %s", resp.Status)
    }
    var parsed struct {
        Choices []struct {
            Message struct {
                Content string `json:"content"`
            } `json:"message"`
        } `json:"choices"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
        return nil, err
    }
    if len(parsed.Choices) == 0 {
        return nil, fmt.Errorf("unexpected groq response")
    }
    lines := strings.Split(parsed.Choices[0].Message.Content, "\n")
    return filterEmpty(lines), nil
}

func filterEmpty(in []string) []string {
    out := make([]string, 0, len(in))
    for _, v := range in {
        if s := strings.TrimSpace(v); s != "" {
            out = append(out, s)
        }
    }
    return out
}

func batch(slice []string, size int) [][]string {
    var batches [][]string
    for size < len(slice) {
        slice, batches = slice[size:], append(batches, slice[0:size:size])
    }
    batches = append(batches, slice)
    return batches
}

func main() {
    var (
        inputFile     string
        configFile    string
        batchSize     int
        outputFile    string
        promptFlag    string
        directoryMode bool
        domainMode    bool
        disableSSL    bool
        concurrency   int
    )

    flag.StringVar(&inputFile, "f", "", "Input file with domains/URLs")
    flag.StringVar(&configFile, "c", "", "Config JSON with API keys")
    flag.IntVar(&batchSize, "b", 100, "Batch size")
    flag.StringVar(&outputFile, "o", "", "Output file")
    flag.StringVar(&promptFlag, "p", "", "Custom prompt")
    flag.BoolVar(&directoryMode, "d", false, "Directory mode")
    flag.BoolVar(&domainMode, "s", false, "Subdomain mode")
    flag.BoolVar(&disableSSL, "disable_ssl", false, "Disable SSL verification")
    flag.IntVar(&concurrency, "t", 10, "Max concurrent requests")
    flag.Parse()

    if inputFile == "" || configFile == "" {
        fmt.Println("input file (-f) and config (-c) are required")
        os.Exit(1)
    }

    cfgFile, err := os.Open(configFile)
    if err != nil {
        panic(err)
    }
    defer cfgFile.Close()
    var cfg Config
    if err := json.NewDecoder(cfgFile).Decode(&cfg); err != nil {
        panic(err)
    }

    infile, err := os.Open(inputFile)
    if err != nil {
        panic(err)
    }
    defer infile.Close()
    scanner := bufio.NewScanner(infile)
    var entries []string
    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())
        if line != "" {
            entries = append(entries, line)
        }
    }
    if scanner.Err() != nil {
        panic(scanner.Err())
    }

    prompt := promptFlag
    if prompt == "" {
        switch {
        case domainMode:
            prompt = fmt.Sprintf("There are %%d subdomains separated by a < character. Based on the sample subdomains, generate 150 new possible subdomains. Only return the subdomains. Do not number them.")
        case directoryMode:
            prompt = fmt.Sprintf("There are %%d URLs separated by a < character. Based on the sample URLs and folders, generate 150 new possible directory paths. Only return the directory paths. Do not number them or place any formatting.")
        default:
            prompt = "Generate related wordlist entries:"
        }
    }

    var outFile *os.File
    if outputFile != "" {
        outFile, err = os.Create(outputFile)
        if err != nil {
            panic(err)
        }
        defer outFile.Close()
    }

    httpClient := &http.Client{
        Timeout: 60 * time.Second,
    }
    if disableSSL {
        httpClient.Transport = &http.Transport{
            TLSClientConfig: &tls.Config{InsecureSkipVerify: true}, //nolint:gosec
        }
    }

    apis := []apiFunc{geminiRequest, deepseekRequest, groqRequest}
    var counter uint32 = 0

    sem := make(chan struct{}, concurrency)
    var wg sync.WaitGroup
    var mu sync.Mutex

    for _, b := range batch(entries, batchSize) {
        wg.Add(1)
        sem <- struct{}{}
        go func(batch []string) {
            defer wg.Done()
            defer func() { <-sem }()
            idx := atomic.AddUint32(&counter, 1) - 1
            api := apis[int(idx)%len(apis)]
            batchText := strings.Join(batch, "<")
            fullPrompt := fmt.Sprintf(prompt, len(batch)) + " " + batchText

            ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
            defer cancel()
            respCh := make(chan []string, 1)
            errCh := make(chan error, 1)

            go func() {
                res, err := api(fullPrompt, &cfg, httpClient)
                if err != nil {
                    errCh <- err
                    return
                }
                respCh <- res
            }()

            select {
            case <-ctx.Done():
                fmt.Printf("[!] timeout for batch starting %s\n", batch[0])
            case err := <-errCh:
                fmt.Printf("[!] error: %v\n", err)
            case res := <-respCh:
                mu.Lock()
                if outFile != nil {
                    for _, line := range res {
                        fmt.Fprintln(outFile, line)
                    }
                }
                mu.Unlock()
                fmt.Printf("[+] Generated %d entries\n", len(res))
            }
        }(b)
    }
    wg.Wait()
}

