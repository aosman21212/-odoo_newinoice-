Quick Start Commands
1. Build the Docker Image
First, navigate to the directory containing your docker-compose.yml file, then build the Docker image:
bashdocker-compose build
2. Run the Docker Container
Start the container in detached mode (running in the background):
bashdocker-compose up -d
3. View Logs
Monitor the logs of the running container in real-time:
bashdocker-compose logs -f
4. Stop the Container
Stop and remove the containers, networks, and volumes:
bashdocker-compose down
Command Explanations
docker-compose build

Builds or rebuilds the services defined in your docker-compose.yml file
Pulls necessary images and prepares them according to your configuration
Use this when you've made changes to your Dockerfile or build context

docker-compose up -d

Starts containers in detached mode (-d flag)
Containers run in the background, freeing up your terminal
Creates networks and volumes as defined in your compose file

docker-compose logs -f

Displays logs from all running containers
The -f flag follows log output in real-time (similar to tail -f)
Useful for debugging and monitoring application behavior

docker-compose down

Stops and removes containers created by docker-compose up
Removes networks created by the compose file
Optionally removes volumes (depending on configuration)
