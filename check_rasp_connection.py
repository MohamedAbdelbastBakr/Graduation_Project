import os
from re import findall
from subprocess import Popen, PIPE

def get_ip_from_arp(mac_address):
    # Run arp -a command to get ARP table
    arp_output = os.popen('arp -a').read()
    
    # Split the output into lines
    arp_lines = arp_output.split('\n')
    
    ip_address = []
    # Iterate over each line
    for line in arp_lines:
        # Check if the MAC address is present in the line
        if mac_address in line:
            # Split the line into parts
            parts = line.split()
            # Extract the IP address (it should be the second element)
            ip_address.append(parts[0])
    return ip_address

def ping (host,ping_count=4):

    for ip in host:
        data = ""
        output= Popen(f"ping {ip} -n {ping_count}", stdout=PIPE, encoding="utf-8")

        for line in output.stdout:
            data = data + line
            ping_test = findall("TTL", data)

        if ping_test:
            continue
        else:
            return False
    return True

# Example MAC address
#mac_to_check = '28-cd-c1-0e-7b-55'

def check(MAC='28-cd-c1-0e-7b-55'):
    ip_address = get_ip_from_arp(MAC)
    if len(ip_address)!=0:
        print("IP address of device with MAC address {} is {}.".format(MAC, ip_address))
        if(ping(ip_address)):
            print("device connected.")
            return True
        else:
            print("device is not connected!")
            return False
    else:
        print("Device with MAC address {} is not found in the ARP table.".format(MAC))
        return False

    