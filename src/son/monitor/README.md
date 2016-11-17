# son-monitor

Monitor metrics of a deployed service (from the SONATA SDK emulator or Service Platform).
Generate and/or export metrics that are useful for debugging and analyzing the service performance.

Below figure shows the architecture of the son-monitor tools inside the total SONATA SDK:
- A set of monitoring functions implemented in son-emu
- External docker containers to gather and store metrics (cAdvisor, Prometheus)
- Metric install and retrieval functions inside son-cli

![son-monitor](../../../figures/Son-monitor-architecturev3.png)


```
usage: son-monitor [-h] [--vnf_names [VNF_NAMES [VNF_NAMES ...]]] [--vim VIM]
                   [--vnf_name VNF_NAME] [--datacenter DATACENTER]
                   [--image IMAGE] [--dcmd DOCKER_COMMAND] [--net NETWORK]
                   [--query QUERY] [--input INPUT] [--output OUTPUT]
                   [--source SOURCE] [--destination DESTINATION]
                   [--weight WEIGHT] [--match MATCH] [--bidirectional]
                   [--priority PRIORITY] [--metric METRIC] [--cookie COOKIE]
                   [--file FILE]
                   
                   {init,profile,query,interface,flow_mon,flow_entry,flow_total,msd,dump,xterm}
                   [{start,stop}]

    Install monitor features on or get monitor data from the SONATA platform/emulator.
    

positional arguments:
  {init,profile,query,interface,flow_mon,flow_entry,flow_total,msd,dump,xterm}
                        Monitoring feature to be executed:
                                 interface: export interface metric (tx/rx bytes/packets)
                                 flow_entry : (un)set the flow entry
                                 flow_mon : export flow_entry metric (tx/rx bytes/packets)
                                 flow_total : flow_entry + flow_mon
                                 init : start/stop the monitoring framework
                                 msd :  start/stop monitoring metrics from the msd (monitoring descriptor file)
                                 profile : performance profiling (tba)
                                 dump: start tcpdump for specified interface (save as .pcap)
                                 xterm: start an xterminal for specific vnf(s)
                                 
  {start,stop}          Action for interface, flow_mon, flow_entry, flow_total:
                                  start: install the flowentry and/or export the metric
                                  stop: delete the flowentry and/or stop exporting the metric
                                  Action for init:
                                  start: start the monitoring framework (cAdvisor, Prometheus DB + Pushgateway)
                                  stop: stop the monitoring framework
                                  Action for nsd:
                                  start: start the monitoring metrics from the nsd
                                  stop: start the monitoring metrics from the nsd
                                  Action for xterm:
                                  vnf names to start an xterm for
                                  

optional arguments:
  -h, --help            show this help message and exit
  --vnf_names [VNF_NAMES [VNF_NAMES ...]], -n [VNF_NAMES [VNF_NAMES ...]]
                        vnf names to open an xterm for
  --vim VIM, -v VIM     VIM where the command should be executed (emu/sp)
  --vnf_name VNF_NAME, -vnf VNF_NAME
                        vnf name:interface to be monitored
  --datacenter DATACENTER, -d DATACENTER
                        Data center where the vnf is deployed
  --image IMAGE, -i IMAGE
                        Name of container image to be used e.g. 'ubuntu:trusty'
  --dcmd DOCKER_COMMAND, -cmd DOCKER_COMMAND
                        Startup command of the container e.g. './start.sh'
  --net NETWORK         Network properties of a compute instance e.g.           '(id=input,ip=10.0.10.3/24),(id=output,ip=10.0.10.4/24)' for multiple interfaces.
  --query QUERY, -q QUERY
                        prometheus query
  --input INPUT, -in INPUT
                        input interface of the vnf to profile
  --output OUTPUT, -out OUTPUT
                        output interface of the vnf to profile
  --source SOURCE, -src SOURCE
                        vnf name:interface of the source of the chain
  --destination DESTINATION, -dst DESTINATION
                        vnf name:interface of the destination of the chain
  --weight WEIGHT, -w WEIGHT
                        weight edge attribute to calculate the path
  --match MATCH, -ma MATCH
                        string holding extra matches for the flow entries
  --bidirectional, -b   add/remove the flow entries from src to dst and back
  --priority PRIORITY, -p PRIORITY
                        priority of the installed flowrule
  --metric METRIC, -me METRIC
                        tx_bytes, rx_bytes, tx_packets, rx_packets
  --cookie COOKIE, -c COOKIE
                        flow cookie to monitor
  --file FILE, -f FILE  service descriptor file describing monitoring rules

```


This command starts an xterm for all deployed docker VNFs in son-emu (if no names are specified, xterms for all vnfs are started)
```
son-monitor xterm [-n vnf_names]
```

After a service has been deployed on the SDK emulator (son-emu), son-monitor can be used.
Son-monitor uses the son-emu rest api and Prometheus.

This command installs the metrics defined in a monitorign specific descriptor file 
and starts all the related docker files (Grafana, Prometheus DB). A new Grafana dashboard is started where the defined metrics are shown.
This is the recommended usage for son-monitor.
```
son-monitor msd -f file.yml
```

The commands executed in this file can also be executed separately:

*Example1*: Expose the tx_packets metric from son-emu network switch-port where vnf1 (default 1st interface) is connected.
The metric is exposed to the Prometheus DB.
```
son-monitor son-monitor interface start -vnf vnf1 -me tx_packets
```

*Example2*: Install a flow_entry in son-emu, monitor the tx_bytes on that flow_entry.
The metric is exposed to the Prometheus DB.
```
son-monitor flow_total start -src vnf1  -dst vnf2  -ma "dl_type=0x0800,nw_proto=17,udp_dst=5001"  -b -c 11 -me tx_bytes
```

*Example3*:  Send a query to the prometheus DB to retrieve the earlier exposed metrics, or default metric exposed by cAdvisor.
The Prometheus query language can be used.
```
son-monitor query --vim emu -d datacenter1 -vnf vnf1 -q 'sum(rate(container_cpu_usage_seconds_total{id="/docker/<uuid>"}[10s]))'
```
