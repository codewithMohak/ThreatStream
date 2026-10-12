package main

import (
	"encoding/csv"
	"fmt"
	"math/rand"
	"os"
	"strconv"
	"time"
)

func main() {
	rng := rand.New(rand.NewSource(42))

	file, err := os.Create("data/access_logs.csv")
	if err != nil {
		fmt.Println("Error creating log file:", err)
		return
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	header := []string{
		"timestamp", "ip", "method",
		"endpoint", "status", "response_bytes",
	}

	if err := writer.Write(header); err != nil {
		fmt.Println("Error writing header:", err)
		return
	}

	normalIPs := []string{
		"192.168.1.10",
		"192.168.1.11",
		"192.168.1.12",
		"192.168.1.13",
		"192.168.1.14",
	}

	endpoints := []string{
		"/", "/login", "/products",
		"/about", "/contact", "/api/users",
	}

	start := time.Now().Add(-60 * time.Minute)
	total := 1500

	for i := 0; i < total; i++ {
		ts := start.Add(time.Duration(i*2) * time.Second)
		ip := normalIPs[rng.Intn(len(normalIPs))]
		method := "GET"
		endpoint := endpoints[rng.Intn(len(endpoints))]
		status := 200
		size := rng.Intn(4500) + 300

		// Simulated repeated login failures.
		if i%37 == 0 {
			ip = "203.0.113.50"
			endpoint = "/login"
			status = 401
			method = "POST"
		}

		// Simulated endpoint scanning.
		if i%41 == 0 {
			ip = "198.51.100.77"
			endpoint = []string{
				"/admin", "/.env", "/wp-login.php",
				"/config", "/backup",
			}[rng.Intn(5)]
			status = 404
		}

		// Simulated forbidden access.
		if i%53 == 0 {
			ip = "203.0.113.88"
			endpoint = "/admin"
			status = 403
		}

		record := []string{
			ts.Format(time.RFC3339),
			ip,
			method,
			endpoint,
			strconv.Itoa(status),
			strconv.Itoa(size),
		}

		if err := writer.Write(record); err != nil {
			fmt.Println("Error writing log:", err)
			return
		}
	}

	writer.Flush()
	if err := writer.Error(); err != nil {
		fmt.Println("Error saving log:", err)
		return
	}

	fmt.Printf("Success! Generated %d web access log records.\n", total)
	fmt.Println("File: data/access_logs.csv")
}
