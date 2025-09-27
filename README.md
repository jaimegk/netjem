

# Network Emulation API (NetJem)

A REST API based on FastAPI that allows emulating network conditions using Linux Traffic Control (tc) for testing and network simulation.

## Features

- **Latency Emulation**: Adds configurable delays to packets.
- **Packet Loss**: Simulates random packet loss (0-100%).
- **Data Corruption**: Introduces random errors in packets.
- **Packet Duplication**: Simulates random packet duplication.
- **Bandwidth Control**: Limits the transmission speed.
- **IP Filtering**: Applies emulation only to specific IP addresses.
- **ARP Scan**: Discovers active devices on the network.
- **Interface Management**: Handles multiple network interfaces.

## System Requirements

### Hardware
- x86_64 or ARM64 architecture
- Minimum 512MB RAM available
- Access to host network interfaces

### Software
- **Linux**: Ubuntu 18.04+, Debian 9+, CentOS 7+, or compatible distributions.
- **Docker**: Version 20.10 or higher.
- **Permissions**: Superuser access (root/sudo).

### Platform Compatibility
- ✅ **Native Linux**: Full functionality.
- ⚠️ **Windows with WSL2**: Limited functionality, as `tc` only affects the WSL2 subsystem.
- ⚠️ **macOS**: Limited functionality, as `tc` only affects the Docker container.
- ❌ **Native Windows**: Not compatible with traffic control.

## Installation and Execution

### Step 1: Get the code
```bash
git clone <repository_url>
cd TSDocker
```

### Step 2: Build the Docker image
```bash
# Recommended option (optimized image)
docker build -f Dockerfile.multistage -t netjem-api .

# Alternative option (simple image)
docker build -t netjem-api .
```

### Step 3: Run the container
```bash
# Execution with full access to the host's network
docker run --privileged --network host netjem-api
```

### Step 4: Verify operation
- API available at: http://localhost:11111/docs

## Execution Parameters

### Required Docker Flags

**`--privileged`**
- **Purpose**: Grants administrative capabilities to the container.
- **Required for**: Executing `tc` (traffic control) commands.
- **Risk**: Full access to the host system.

**`--network host`**
- **Purpose**: Shares the host's network stack with the container.
- **Required for**: `tc` modifications to affect the host's real interfaces.
- **Effect**: The container sees and modifies the system's interfaces directly.

### Advanced Configuration
```bash
# Run in the background
docker run -d --privileged --network host --name netjem netjem-api

# Run with visible logs
docker run --privileged --network host --rm netjem-api

# Run with automatic restart
docker run -d --restart unless-stopped --privileged --network host netjem-api
```

## Security Warnings

### CRITICAL
- **Privileged Permissions**: The container has full access to the host system.
- **Network Modification**: Can significantly alter network behavior.
- **Service Interruptions**: Incorrect configurations can cause loss of connectivity.

### IMPORTANT
- **Development/Testing Only**: Not recommended for production environments without supervision.
- **Configuration Backups**: Ensure you can restore the original network configuration.
- **Monitoring**: Supervise the impact on network performance during tests.

### OPERATIONAL
- **Persistence**: `tc` configurations are lost upon system reboot.
- **Conflicts**: May interfere with other network management tools (NetworkManager, systemd-networkd).
- **Resources**: Traffic shaping can aggressively affect network communications. It is always recommended to perform a cleanup after experimentation is finished.

## Installation Validation

### Verify system capabilities
```bash
# Check that tc is available
docker run --privileged --network host --rm netjem-api tc qdisc show

# Verify available network interfaces
docker run --privileged --network host --rm netjem-api ip link show

# Test API connectivity
curl http://localhost:11111/interfaces_info
```

## Native Execution (Alternative)

For Linux systems without Docker:

### Install dependencies
```bash
sudo apt update
sudo apt install python3 python3-pip iproute2
```

### Configure Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run application
```bash
sudo python -m uvicorn NetJemAPI:app --host 0.0.0.0 --port 11111
```

## Troubleshooting

### Error: "tc: command not found"
```bash
# Rebuild image without cache
docker build -f Dockerfile.multistage -t netjem-api --no-cache .
```

### Error: "Permission denied"
```bash
# Verify that Docker has sudo permissions
sudo docker run --privileged --network host netjem-api
```

### Error: "Cannot bind to port 11111"
```bash
# Check if the port is in use
sudo netstat -tulpn | grep 11111
# Or use a different port
docker run --privileged --network host -e PORT=8080 netjem-api
```

## API Usage

Once running, access:
- **Interactive Documentation**: http://localhost:11111/docs
- **OpenAPI Specification**: http://localhost:11111/openapi.json

## Technical Limitations

1. **Platform**: Requires a Linux kernel with `tc` support.
2. **Permissions**: Needs administrative privileges.
3. **Network**: Modifications affect all system traffic.
4. **Persistence**: Temporary configurations (lost on reboot).
5. **Concurrency**: Only one control point per network interface.
