package main

import (
	"context"
	"fmt"
	"net/http"
	"os/exec"
)

var n int

func main() {
	mux := http.NewServeMux()
	srv := http.Server{
		Addr:    "0.0.0.0:8080",
		Handler: mux,
	}
	mux.HandleFunc("/shutdown_the_pc", func(w http.ResponseWriter, r *http.Request) {

		n++
		if n > 10 {
			w.Write([]byte(`{"response": "Shutting down..."}`))

			out, err := exec.Command("systemctl", "poweroff").Output()

			if err != nil {
				fmt.Printf("%s", err)
			}

			fmt.Println("Command Successfully Executed")
			output := string(out[:])
			fmt.Println(output)

			go srv.Shutdown(context.Background())
		} else {
			w.Write([]byte(`{"response": "Reload the page"}`))
		}

	})

	fmt.Println("Up and running")

	if err := srv.ListenAndServe(); err != http.ErrServerClosed {
		panic(err)
	}
}
