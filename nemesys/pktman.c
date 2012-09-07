
#include <headers.h>

struct device
{
  int   index;
  int   type;
  char  *description;
  char  *name;
  char  *mac;
  char  *ip;
  char  *net;
  char  *mask;
};

char *sniff_error[] =
{
  "Timeout was reached during packet receive",
  "One packet pulled",
  "Packet out of range",
  "Error receiving the packet",
};

struct statistics
{
  u_long  pkt_pcap_proc;
  u_long  pkt_pcap_tot;
  u_long  pkt_pcap_drop;
  u_long  pkt_pcap_dropif;
};

int DEBUG_MODE=0;
FILE *debug_log;

char *dump_file;

int err_flag=0;
char err_str[88]="No Error";

PyGILState_STATE gil_state;
PyObject *py_pkt_header, *py_pkt_data;

u_int no_stop=0, num_dev=0, online=1;
u_int pkt_start=0, pkt_stop=0;

int data_link=0, sniff_mode=0;

pcap_t *handle;

struct device devices[22];
struct pcap_stat pcapstat;
struct statistics stats;


void print_hex_ascii_line(const u_char *payload, int len, int offset, char *packet)
{
  int i;
  int gap;
  const u_char *ch;
  char buffer[22];

  /* offset */
  sprintf(buffer,"| %05d |  ", offset);
  strcat(packet,buffer);

  /* hex */
  ch = payload;
  for(i = 0; i < len; i++)
  {
    sprintf(buffer,"%02x ", *ch);
    strcat(packet,buffer);
    ch++;
    /* print extra space after 8th byte for visual aid */
    if (i == 7) {strcat(packet," ");}
  }
  /* print space to handle line less than 8 bytes */
  if (len < 8) {strcat(packet," ");}

  /* fill hex gap with spaces if not full line */
  if (len < 16)
  {
    gap = 16 - len;
    for (i = 0; i < gap; i++) {strcat(packet,"   ");}
  }
  strcat(packet," | ");

  /* ascii (if printable) */
  ch = payload;
  for(i = 0; i < len; i++)
  {
    if (isprint(*ch))
    {
      sprintf(buffer,"%c", *ch);
      strcat(packet,buffer);
    }
    else {strcat(packet,".");}
    ch++;
  }

  if (len < 16)
  {
    gap = 16 - len;
    for (i = 0; i < gap; i++) {strcat(packet,".");}
  }
  strcat(packet," |\n");

  return;
}


void print_payload(const u_char *payload, int len)
{
  int len_rem = len;
  int line_width = 16;      /* number of bytes per line */
  int line_len;
  int offset = 0;          /* zero-based offset counter */
  const u_char *ch = payload;
  char *packet;

  packet = PyMem_New(char,88*((len/line_width)+1));

  strcpy(packet,"\n");

  if (len <= 0) {return;}

  /* data fits on one line */
  if (len <= line_width)
  {
    print_hex_ascii_line(ch, len, offset, packet);
    return;
  }

  /* data spans multiple lines */
  for ( ;; )
  {
    /* compute current line length */
    line_len = line_width % len_rem;
    /* print line */
    print_hex_ascii_line(ch, line_len, offset, packet);
    /* compute total remaining */
    len_rem = len_rem - line_len;
    /* shift pointer to remaining bytes to print */
    ch = ch + line_len;
    /* add offset */
    offset = offset + line_width;
    /* check if we have line width chars or less */
    if (len_rem <= line_width)
    {
      /* print last line and get out */
      print_hex_ascii_line(ch, len_rem, offset, packet);
      break;
    }
  }

  fprintf(debug_log,"%s",packet);

  PyMem_Free(packet);

  return;
}


void setfilter(const char *filter)
{
  bpf_u_int32 netp, maskp;

  struct bpf_program filterprog;

  char errbuf[PCAP_ERRBUF_SIZE];

  if (pcap_lookupnet(devices[num_dev].name, &netp, &maskp, errbuf) != 0)
  {sprintf (err_str,"LookUpNet Warnings: %s", errbuf);err_flag=0;}

  if (pcap_compile(handle,&filterprog,filter,0,maskp) == -1)
  {sprintf(err_str,"Error in pcap_compile filter");err_flag=-1;return;}

  if(pcap_setfilter(handle,&filterprog) == -1)
  {sprintf(err_str,"Error setting filter");err_flag=-1;return;}

  pcap_freecode(&filterprog);

  /* DEBUG BEGIN */
  if(DEBUG_MODE)
  {
    debug_log = fopen("pktman.txt","a");

    fprintf(debug_log,"\nfiltro: %s \n",filter);

    fclose(debug_log);
    debug_log = NULL;
  }
  /* DEBUG END */
}


void mydump(u_char *dumpfile, const struct pcap_pkthdr *pcap_header, const u_char *pcap_data)
{
  pcap_dump(dumpfile, pcap_header, pcap_data);

  stats.pkt_pcap_proc++;

  /* DEBUG BEGIN */
  if(DEBUG_MODE)
  {
    debug_log = fopen("pktman.txt","a");

    fprintf(debug_log,"\n[My Dump - Packet Number %08li]\n",stats.pkt_pcap_proc);

    fclose(debug_log);
    debug_log = NULL;
  }
  /* DEBUG END */
}


void dumper(void)
{
  pcap_dumper_t *dumpfile;

  pcap_stats(handle,&pcapstat);

  if((pcapstat.ps_drop)>0 || (pcapstat.ps_ifdrop)>0)
  {
    pcapstat.ps_drop=0;
    pcapstat.ps_ifdrop=0;
  }

  dumpfile = pcap_dump_open(handle,dump_file);

  if (dumpfile == NULL)
  {sprintf(err_str,"Error opening savefile %s for writing: %s",dump_file, pcap_geterr(handle));err_flag=-1;return;}

  /* DEBUG BEGIN */
  if(DEBUG_MODE)
  {
    debug_log = fopen("pktman.txt","a");

    fprintf(debug_log,"\n[Infinite Loop]\n");

    fclose(debug_log);
    debug_log = NULL;
  }
  /* DEBUG END */

  if (pcap_loop(handle, sniff_mode, mydump, (u_char *)dumpfile) == -1)
  {sprintf(err_str,"Pcap loop error: %s",pcap_geterr(handle));err_flag=-1;return;}

  pcap_stats(handle,&pcapstat);

  stats.pkt_pcap_tot=pcapstat.ps_recv;
  stats.pkt_pcap_drop=pcapstat.ps_drop;
  stats.pkt_pcap_dropif=pcapstat.ps_ifdrop;

  pcap_close(handle);

  pcap_dump_close(dumpfile);
}


int sniffer()
{
  int sniff_status=0;

  struct pcap_pkthdr *pcap_header;
  const u_char *pcap_data;

  struct tm *ts;
  time_t timestamp;
  char timestamp_string[44];

  no_stop=1;

  py_pkt_header = Py_None;
  py_pkt_data = Py_None;

  if (handle != NULL)
  {
    sniff_status=pcap_next_ex(handle,&pcap_header,&pcap_data);

    switch (sniff_status)
    {
      case  0 : sniff_status=0;
                break;

      case -1 : sniff_status=3;
                //sprintf(err_str,"Error reading the packet: %s",pcap_geterr(handle));
                break;

      case -2 : sniff_status=3;
                //sprintf(err_str,"Error reading the packet: %s",pcap_geterr(handle));
                break;

      default : sniff_status=1;

                if ((sniff_mode>0) && (pcap_header!=NULL) && (pcap_data!=NULL))
                {
                  py_pkt_header = PyString_FromStringAndSize((const char *)pcap_header,sizeof(struct pcap_pkthdr));

                  if (data_link!=113)
                  {py_pkt_data = PyString_FromStringAndSize((const char *)pcap_data,(pcap_header->caplen));}
                  else
                  {py_pkt_data = PyString_FromStringAndSize((const char *)pcap_data+2,(pcap_header->caplen)-2);}

                  if ((py_pkt_header==NULL) || (py_pkt_data==NULL))
                  {
                      py_pkt_header = Py_None;
                      py_pkt_data = Py_None;
                  }
                }

                if(online==1)
                {
                  pcap_stats(handle,&pcapstat);

                  if((stats.pkt_pcap_proc==0) && ((pcapstat.ps_drop)>0 || (pcapstat.ps_ifdrop)>0))
                  {
                    pcapstat.ps_drop=0;
                    pcapstat.ps_ifdrop=0;
                  }

                  stats.pkt_pcap_tot=pcapstat.ps_recv;
                  stats.pkt_pcap_drop=pcapstat.ps_drop;
                  stats.pkt_pcap_dropif=pcapstat.ps_ifdrop;
                }

                stats.pkt_pcap_proc++;

                if (pkt_stop>pkt_start && pkt_stop>0)
                {
                  if (stats.pkt_pcap_proc<pkt_start || stats.pkt_pcap_proc>pkt_stop)
                  {
                    py_pkt_header = Py_None;
                    py_pkt_data = Py_None;
                    sniff_status=2;
                  }
                }

                /* DEBUG BEGIN */
                if(DEBUG_MODE)
                {
                  debug_log = fopen("pktman.txt","a");

                  timestamp = pcap_header->ts.tv_sec;
                  ts=localtime(&timestamp);
                  strftime(timestamp_string, sizeof(timestamp_string), "%a %Y/%m/%d %H:%M:%S", (const struct tm *) ts);

                  fprintf(debug_log,"\n\n[Packet: %08li][CapLen: %04i][Len: %04i][Time: %s.%.6d]\n",stats.pkt_pcap_proc,(pcap_header->caplen),(pcap_header->len),timestamp_string,(int)(pcap_header->ts.tv_usec));
                  fprintf(debug_log,"=================================================================================");
                  print_payload(pcap_data,pcap_header->caplen);
                  fprintf(debug_log,"=================================================================================");

                  fclose(debug_log);
                  debug_log = NULL;
                }
                /* DEBUG END */

                break;
    }
  }
  else
  {
    sprintf(err_str,"Couldn't receive any packet: No Hadle Active on Networks Interfaces");err_flag=-1;

    py_pkt_header = Py_None;
    py_pkt_data = Py_None;
  }

  // DEBUG-BEGIN
  if(DEBUG_MODE)
  {;}
  // DEBUG-END

  no_stop=0;

  return sniff_status;
}


u_int dot_to_int(const char *dot)
{
  u_int res;
  u_int dot1,dot2,dot3,dot4;

  if (sscanf(dot,"%u.%u.%u.%u", &dot1, &dot2, &dot3, &dot4) == 4)
  {
    res=(dot1*16777216)+(dot2*65536)+(dot3*256)+(dot4*1);
    return res;
  }

  return 0;
}


char *int_to_dot(u_int address, char *res)
{
  u_int i;
  u_int addr;
  u_int dot[4];
  u_int base[4] = {16777216, 65536, 256, 1};

  for(i = 0; i <= 3 ; i++)
  {
    addr = address;
    dot[i] = addr / base[i];
    address = addr % base[i];
  }
  sprintf(res,"%u.%u.%u.%u",dot[0],dot[1],dot[2],dot[3]);

  return res;
}


char *cidr_to_dot(u_long cidr, char *mask)
{
  char *mask255 = "255.255.255.255";
  double ui_net = 0;
  u_int ui_mask=0, ui_mask255=0;
  u_int i, bits;

  bits = 32 - (u_int)cidr;
  ui_mask255 = dot_to_int(mask255);

  for(i = 0; i < bits ; i++)
  {ui_net += pow(2,(double)i);}

  ui_mask = ui_mask255 - (u_int)ui_net;
  mask = int_to_dot(ui_mask, mask);

  return mask;
}


int ip_in_net(const char *ip, const char *net, const char *mask)
{
  char *mask255 = "255.255.255.255";
  char *net0 = "0.0.0.0";

  u_int ui_ip=0, ui_net=0, ui_mask=0;

  ui_ip = dot_to_int(ip);
  ui_net = dot_to_int(net);
  ui_mask = dot_to_int(mask);

  if (((ui_ip & ui_mask) == (ui_net & ui_mask)) && (ui_mask!=0))
  {return 1;}
  else if ((strcmp(mask,mask255)==0) && !(strcmp(net,net0)==0))
  {return 1;}
  else
  {return 0;}
}


u_int find_devices(void)
{
  u_int tot_dev=0;

  int IpInNet=0;
  int if_sock;

  char *ip, *net, *mask;
  char errbuf[PCAP_ERRBUF_SIZE];

  struct in_addr addr;
  struct ifreq if_struct;

  bpf_u_int32 netp=0, maskp=0;

  pcap_if_t *alldevs, *dl;

  tot_dev=0;

  if_sock = socket(AF_INET, SOCK_DGRAM, 0);

  if (pcap_findalldevs (&alldevs, errbuf) != 0)
  {sprintf(err_str,"FindAllDevs error: %s",errbuf);err_flag=-1;return tot_dev;}

  if (alldevs == NULL)
  {sprintf(err_str,"No Sniffable Device or User Without Root Permissions");err_flag=-1;return tot_dev;}

  dl=alldevs;

  for(dl=alldevs; dl; dl=dl->next)
  {
    tot_dev++;

    devices[tot_dev].index = tot_dev;

    devices[tot_dev].name = PyMem_New(char,strlen(dl->name)+1);
    memcpy(devices[tot_dev].name,dl->name,strlen(dl->name)+1);

    if (strstr(devices[tot_dev].name,"eth")!=NULL)
    {devices[tot_dev].type = 14;}
    else if (strstr(devices[tot_dev].name,"wlan")!=NULL)
    {devices[tot_dev].type = 25;}
    else if (strstr(devices[tot_dev].name,"ppp")!=NULL)
    {devices[tot_dev].type = 17;}
    else
    {devices[tot_dev].type = 0;}

    if (dl->description != NULL)
    {
      devices[tot_dev].description = PyMem_New(char,strlen(dl->description)+1);
      memcpy(devices[tot_dev].description,dl->description,strlen(dl->description)+1);
    }
    else
    {
      devices[tot_dev].description = PyMem_New(char,8*sizeof(char));
      devices[tot_dev].description = "none";
    }

    strncpy(if_struct.ifr_name, devices[tot_dev].name, sizeof(if_struct.ifr_name));
    devices[tot_dev].mac = "--:--:--:--:--:--";
    if (ioctl (if_sock, SIOCGIFHWADDR, &if_struct) < 0)
    {
      /* DEBUG BEGIN */
      if(DEBUG_MODE)
      {
        debug_log = fopen("pktman.txt","a");

        fprintf(debug_log,"SIOCGIFHWADDR(%s): %m\n",if_struct.ifr_name);

        fclose(debug_log);
        debug_log = NULL;
      }
      /* DEBUG END */
    }
    else
    {
      devices[tot_dev].mac = PyMem_New(char,18*sizeof(char));
      sprintf(devices[tot_dev].mac,"%02X:%02X:%02X:%02X:%02X:%02X",
      (int) ((unsigned char *) &if_struct.ifr_hwaddr.sa_data)[0],
      (int) ((unsigned char *) &if_struct.ifr_hwaddr.sa_data)[1],
      (int) ((unsigned char *) &if_struct.ifr_hwaddr.sa_data)[2],
      (int) ((unsigned char *) &if_struct.ifr_hwaddr.sa_data)[3],
      (int) ((unsigned char *) &if_struct.ifr_hwaddr.sa_data)[4],
      (int) ((unsigned char *) &if_struct.ifr_hwaddr.sa_data)[5]);
    }

    if (pcap_lookupnet(dl->name, &netp, &maskp, errbuf) != 0)
    {sprintf (err_str,"LookUpNet Warnings: %s", errbuf);err_flag=0;}

    if (netp!=0)
    {
      addr.s_addr = netp;
      net = inet_ntoa(addr);
      devices[tot_dev].net=PyMem_New(char,strlen(net)+1);
      memcpy(devices[tot_dev].net,net,strlen(net)+1);
    }
    else
    {
      devices[tot_dev].net="-.-.-.-";
    }

    if (maskp!=0)
    {
      addr.s_addr = maskp;
      mask = inet_ntoa(addr);
      devices[tot_dev].mask=PyMem_New(char,strlen(mask)+1);
      memcpy(devices[tot_dev].mask,mask,strlen(mask)+1);
    }
    else
    {
      devices[tot_dev].mask="-.-.-.-";
    }

    devices[tot_dev].ip="-.-.-.-";
    if(dl->addresses!=NULL && strstr(devices[tot_dev].name,"ppp")==NULL)
    {
      while(dl->addresses->next)
      {
        addr.s_addr = ((struct sockaddr_in *)(dl->addresses->addr))->sin_addr.s_addr;
        ip = inet_ntoa(addr);

        /* DEBUG BEGIN */
        if(DEBUG_MODE)
        {
          debug_log = fopen("pktman.txt","a");

          fprintf(debug_log,"AddrPcap: %s\n",ip);

          fclose(debug_log);
          debug_log = NULL;
        }
        /* DEBUG END */

        IpInNet = ip_in_net(ip,devices[tot_dev].net,devices[tot_dev].mask);

        if(IpInNet == 1)
        {
          devices[tot_dev].ip=PyMem_New(char,strlen(ip)+1);
          memcpy(devices[tot_dev].ip,ip,strlen(ip)+1);
        }

        dl->addresses=dl->addresses->next;
      }
    }

    if (strcmp("255.255.255.255",devices[tot_dev].mask)==0)
    {devices[tot_dev].ip=devices[tot_dev].net;}

    /* DEBUG BEGIN */
    if(DEBUG_MODE)
    {
      debug_log = fopen("pktman.txt","a");

      fprintf(debug_log,"\t----====[DEVICE N.%02d]====----\n",tot_dev);
      fprintf(debug_log,"\tNAME:\t%s\n",devices[tot_dev].name);
      fprintf(debug_log,"\tDESCR:\t%s\n",devices[tot_dev].description);
      fprintf(debug_log,"\tMAC:\t%s\n",devices[tot_dev].mac);
      fprintf(debug_log,"\tIP:\t%s\n",devices[tot_dev].ip);
      fprintf(debug_log,"\tNET:\t%s\n",devices[tot_dev].net);
      fprintf(debug_log,"\tMASK:\t%s\n",devices[tot_dev].mask);
      fprintf(debug_log,"\tINDEX:\t%d\n",devices[tot_dev].index);
      fprintf(debug_log,"\tMEDIUM:\t%d\n",devices[tot_dev].type);
      fprintf(debug_log,"\t\n");

      fclose(debug_log);
      debug_log = NULL;
    }
    /* DEBUG END */
  }

  pcap_freealldevs(alldevs);
  close(if_sock);

  return tot_dev;
}


u_int select_device(char *dev)
{
  int active=0; //old
  char errbuf[PCAP_ERRBUF_SIZE]; //old

  u_int tot_dev=0, sel_dev=0, indice=0, IpInNet=0;

  int find[22];

  tot_dev = find_devices();
  if(err_flag != 0) {return sel_dev;}

  sel_dev=0;

  /* DEBUG BEGIN */
  if(DEBUG_MODE)
  {
    debug_log = fopen("pktman.txt","a");

    fprintf(debug_log,"\nSEARCHING FOR: %s\n",dev);

    fclose(debug_log);
    debug_log = NULL;
  }
  /* DEBUG END */

  for(sel_dev=1; sel_dev<=tot_dev; sel_dev++)
  {
    IpInNet = ip_in_net(dev,devices[sel_dev].net,devices[sel_dev].mask);

    /* DEBUG BEGIN */
    if(DEBUG_MODE)
    {
      debug_log = fopen("pktman.txt","a");

      fprintf(debug_log,"\nNAME: %s\nIP: %s\nNET: %s\nMASK: %s\nIpInNet: %i\n",devices[sel_dev].name,devices[sel_dev].ip,devices[sel_dev].net,devices[sel_dev].mask,IpInNet);

      fclose(debug_log);
      debug_log = NULL;
    }
    /* DEBUG END */

    if (strstr(devices[sel_dev].name,dev)!=NULL||(strcmp(dev,devices[sel_dev].name)==0)||(strcmp(dev,devices[sel_dev].ip)==0))
    {
      indice++;
      find[indice]=sel_dev;

      /* DEBUG BEGIN */
      if(DEBUG_MODE)
      {
        debug_log = fopen("pktman.txt","a");

        fprintf(debug_log,"\n[%i] Trovato Device n°%i [%s]\n",indice,sel_dev,devices[sel_dev].name);

        fclose(debug_log);
        debug_log = NULL;
      }
      /* DEBUG END */
    }
  }

  sel_dev=0;

  while (indice!=0)
  {
    sel_dev=find[indice];

    /* DEBUG BEGIN */
    if(DEBUG_MODE)
    {
      debug_log = fopen("pktman.txt","a");

      fprintf(debug_log,"\n[%i] Scelto Device n°%i [%s]\n",indice,sel_dev,devices[sel_dev].name);

      fclose(debug_log);
      debug_log = NULL;
    }
    /* DEBUG END */

    indice--;

    if (indice>0)
    {
        if ((handle=pcap_open_live(devices[sel_dev].name,BUFSIZ,1,4000,errbuf)) == NULL)
        {
            if ((handle=pcap_open_live(devices[sel_dev].name,BUFSIZ,0,4000,errbuf)) == NULL)
            {sprintf (err_str,"Couldn't open device: %s",errbuf);err_flag=-1;return sel_dev;}
        }

        active=sniffer(1);

        pcap_stats(handle,&pcapstat);

        //printf("\nActive: %i\tPacchetti: %i\n",active,pcapstat.ps_recv);
        if ((active>0)||(pcapstat.ps_recv > 0))
        {indice=0;}

        err_flag=0; strcpy(err_str,"No Error");
        pcap_close(handle);
    }
  }

  if (sel_dev==0)
  {sprintf(err_str,"Device Not Found or Not Initialized");err_flag=-1;return sel_dev;}

  return sel_dev;
}


void initialize(char *dev, int promisc, int timeout, int snaplen, int buffer)
{
  char errbuf[PCAP_ERRBUF_SIZE];

  memset(&stats,0,sizeof(struct statistics));

  if (online==0)
  {
    handle=pcap_open_offline(dump_file,errbuf);
  }
  else
  {
    num_dev = select_device(dev);
    if(err_flag != 0) {return;}

    if ((handle=pcap_create(devices[num_dev].name,errbuf)) == NULL)
    {sprintf (err_str,"Couldn't open device: %s",errbuf);err_flag=-1;return;}

    if (pcap_set_timeout(handle,timeout) != 0)
    {sprintf(err_str,"Timeout error: %s",pcap_geterr(handle));err_flag=-1;return;}

    if (pcap_set_snaplen(handle,snaplen) != 0)
    {sprintf(err_str,"Snapshot error: %s",pcap_geterr(handle));err_flag=-1;return;}

    if (pcap_set_buffer_size(handle,buffer) !=0)
    {sprintf(err_str,"SetBuffer error: %s",pcap_geterr(handle));err_flag=-1;return;}

    if (pcap_set_promisc(handle,promisc) != 0)
    {sprintf(err_str,"PromiscuousMode error: %s",pcap_geterr(handle));err_flag=-1;return;}

    if (pcap_activate(handle) !=0)
    {
      if (pcap_set_promisc(handle,0) != 0)
      {sprintf(err_str,"PromiscuousMode error: %s",pcap_geterr(handle));err_flag=-1;return;}
      if (pcap_activate(handle) !=0)
      {sprintf(err_str,"Activate error: %s",pcap_geterr(handle));err_flag=-1;return;}
    }

    data_link=pcap_datalink(handle);

    /* DEBUG BEGIN */
    if(DEBUG_MODE)
    {
      debug_log = fopen("pktman.txt","a");

      if(num_dev>0)
      {
        fprintf(debug_log,"\nInitialize Device: %s",dev);
        fprintf(debug_log,"\nData Link Type: %i - %s - %s",data_link,pcap_datalink_val_to_name(data_link),pcap_datalink_val_to_description(data_link));
        fprintf(debug_log,"\nPromisc: %i\tTimeout: %i\tSnaplen: %i\tBuffer: %i",promisc,timeout,snaplen,buffer);
      }

      fclose(debug_log);
      debug_log = NULL;
    }
    /* DEBUG END */
  }
}


//int main()
//{
//  int promisc=1, timeout=1, snaplen=160, buffer=44*1024000;
//
//  int sniff_status=0;
//
//  num_dev = 0;
//
//  if(DEBUG_MODE==0) {DEBUG_MODE=1;}
//
//  /* DEBUG BEGIN */
//  if(DEBUG_MODE)
//  {
//    debug_log = fopen("pktman.txt","w");
//    fclose(debug_log);
//    debug_log = NULL;
//  }
//  /* DEBUG END */
//
//  initialize("ppp0", promisc, timeout, snaplen, buffer);
//
//  sniff_mode = 1;
//
//  while (stats.pkt_pcap_proc < 80)
//  {
//    sniff_status = sniffer();
//    printf("[%d|%li] ",sniff_status,stats.pkt_pcap_proc);
//  }
//
//  if (sniff_mode>=0)
//  {
//    while(no_stop){;}
//
//    pcap_close(handle);
//
//    handle = NULL;
//  }
//  else
//  {
//    pcap_breakloop(handle);
//  }
//
//  return num_dev;
//}


/*----Python----*/

static PyObject *pktman_debugmode(PyObject *self, PyObject *args)
{
  PyArg_ParseTuple(args, "i", &DEBUG_MODE);

  /* if(DEBUG_MODE==0) {DEBUG_MODE=1;} */

  /* DEBUG BEGIN */
  if(DEBUG_MODE)
  {
    debug_log = fopen("pktman.txt","w");
    fclose(debug_log);
    debug_log = NULL;
  }
  /* DEBUG END */

  return Py_BuildValue("i",DEBUG_MODE);
}

static PyObject *pktman_getdev(PyObject *self, PyObject *args)
{
  PyObject *key, *val, *devs = PyDict_New();

  u_int i=0, tot_dev=0, sel_dev=0;

  char *dev=NULL;

  err_flag=0; strcpy(err_str,"No Error");

  PyArg_ParseTuple(args, "|z",&dev);

  if (dev!=NULL)
  {
    sel_dev = select_device(dev);
    if(err_flag != 0)
    {devs = Py_BuildValue ("{s:i,s:s}","err_flag",err_flag,"err_str",err_str);}
    else
    {devs = Py_BuildValue ("{s:i,s:s,s:i,s:i,s:s,s:s,s:s,s:s,s:s,s:s}"
            ,"err_flag",err_flag,"err_str",err_str
            ,"index",devices[sel_dev].index,"type",devices[sel_dev].type
            ,"name",devices[sel_dev].name,"descr",devices[sel_dev].description
            ,"mac",devices[sel_dev].mac,"ip",devices[sel_dev].ip
            ,"net",devices[sel_dev].net,"mask",devices[sel_dev].mask
            );
    }
  }
  else
  {
    tot_dev = find_devices();
    if(err_flag != 0)
    {devs = Py_BuildValue ("{s:i,s:s}","err_flag",err_flag,"err_str",err_str);}
    else
    {
      val = Py_BuildValue("i",err_flag);
      PyDict_SetItemString(devs,"err_flag",val);
      val = Py_BuildValue("s",err_str);
      PyDict_SetItemString(devs,"err_str",val);
      val = Py_BuildValue("i",tot_dev);
      PyDict_SetItemString(devs,"tot_dev",val);

      for(i=1; i<=tot_dev; i++)
      {
        key = Py_BuildValue("i",i);
        val = Py_BuildValue ("{s:i,s:i,s:s,s:s,s:s,s:s,s:s,s:s}"
              ,"index",devices[i].index,"type",devices[i].type
              ,"name",devices[i].name,"descr",devices[i].description
              ,"mac",devices[i].mac,"ip",devices[i].ip
              ,"net",devices[i].net,"mask",devices[i].mask
              );
        PyDict_SetItem(devs,key,val);
      }

      if (key != Py_None)
      {Py_CLEAR(key);}
      if (val != Py_None)
      {Py_CLEAR(val);}
    }
  }

  return devs;
}

static PyObject *pktman_initialize(PyObject *self, PyObject *args)
{
  int promisc=1, timeout=1, snaplen=BUFSIZ, buffer=44*1024000;

  char *dev;

  err_flag=0; strcpy(err_str,"No Error");

  PyArg_ParseTuple(args, "s|iiiiizii", &dev, &buffer, &snaplen, &timeout, &promisc, &online, &dump_file, &pkt_start, &pkt_stop);

  buffer=44*1024000;

  if (dump_file == NULL)
  {
    dump_file = PyMem_New(char,88*sizeof(char));
    dump_file = "myDumpFile.cap";
  }

  if (err_flag == 0)
  {
    Py_BEGIN_ALLOW_THREADS;
    gil_state = PyGILState_Ensure();

    initialize(dev, promisc, timeout, snaplen, buffer);

    PyGILState_Release(gil_state);
    Py_END_ALLOW_THREADS;
  }

  return Py_BuildValue("{s:i,s:s}","err_flag",err_flag,"err_str",err_str);
}

static PyObject *pktman_setfilter(PyObject *self, PyObject *args)
{
  char *filter;

  err_flag=0; strcpy(err_str,"No Error");

  PyArg_ParseTuple(args, "s", &filter);

  if (handle != NULL && filter != NULL)
  {setfilter(filter);}
  else
  {sprintf(err_str,"Couldn't Set Filter: No Hadle Active on Networks Interfaces");err_flag=-1;}

  return Py_BuildValue("{s:i,s:s}","err_flag",err_flag,"err_str",err_str);
}

static PyObject *pktman_push(PyObject *self, PyObject *args)
{
  Py_BEGIN_ALLOW_THREADS;
  gil_state = PyGILState_Ensure();

  PyObject *py_pkt;

  int pkt_size=0;

  u_char *pkt_to_send;

  err_flag=0; strcpy(err_str,"No Error");

  PyArg_ParseTuple(args,"O",&py_pkt);

  pkt_size=(int)PyString_Size(py_pkt);

  pkt_to_send=(u_char*)PyString_AsString(py_pkt);

  if (handle != NULL)
  {
    if (pcap_sendpacket(handle, pkt_to_send, pkt_size) != 0)
    {sprintf(err_str,"Couldn't send the packet: %s",pcap_geterr(handle));err_flag=-1;}
  }
  else
  {
    sprintf(err_str,"Couldn't send any packet: No Hadle Active on Networks Interfaces");err_flag=-1;
  }

//  if((py_pkt->ob_refcnt)>0)
//  {Py_CLEAR(py_pkt);}

  PyGILState_Release(gil_state);
  Py_END_ALLOW_THREADS;

  return Py_BuildValue("{s:i,s:s}","err_flag",err_flag,"err_str",err_str);
}

static PyObject *pktman_pull(PyObject *self, PyObject *args)
{
  int sniff_status=0;   //err_flag=0; strcpy(err_str,"No Error");

  PyArg_ParseTuple(args, "|i", &sniff_mode);

  if (sniff_mode >= 0)
  {
    if (py_pkt_header != Py_None)
    {Py_CLEAR(py_pkt_header);}
    if (py_pkt_data != Py_None)
    {Py_CLEAR(py_pkt_data);}

    Py_BEGIN_ALLOW_THREADS;
    gil_state = PyGILState_Ensure();

    sniff_status = sniffer();

    PyGILState_Release(gil_state);
    Py_END_ALLOW_THREADS;

    return Py_BuildValue("{s:i,s:s,s:i,s:S,s:S}","err_flag",sniff_status,"err_str",sniff_error[sniff_status],"datalink",data_link,"py_pcap_hdr",py_pkt_header,"py_pcap_data",py_pkt_data);
  }
  else
  {
    Py_BEGIN_ALLOW_THREADS;
    gil_state = PyGILState_Ensure();

    sniff_mode = -1;

    dumper();

    PyGILState_Release(gil_state);
    Py_END_ALLOW_THREADS;

    return Py_BuildValue("{s:i,s:s,s:i,s:s}","err_flag",err_flag,"err_str",err_str,"datalink",data_link,"dumpfile",dump_file);
  }
}

static PyObject *pktman_close(PyObject *self)
{
  err_flag=0; strcpy(err_str,"No Error");

  if (sniff_mode>=0)
  {
    while(no_stop){;}

    pcap_close(handle);

    handle = NULL;
  }
  else
  {
    pcap_breakloop(handle);
  }

  return Py_BuildValue("{s:i,s:s}","err_flag",err_flag,"err_str",err_str);
}

static PyObject *pktman_getstat(PyObject *self)
{
  char request_time[44];
  struct tm *rt;
  time_t req_time;

  if (handle != NULL && online==1)
  {
    pcap_stats(handle,&pcapstat);

    stats.pkt_pcap_tot=pcapstat.ps_recv;
    stats.pkt_pcap_drop=pcapstat.ps_drop;
    stats.pkt_pcap_dropif=pcapstat.ps_ifdrop;
  }

  req_time=time(0);
  rt=localtime(&req_time);
  strftime(request_time, sizeof request_time, "%a %Y/%m/%d %H:%M:%S", (const struct tm *) rt);

  return Py_BuildValue("{s:s,s:l,s:l,s:l,s:l}",
                       "stat_time",request_time,"pkt_pcap_proc",stats.pkt_pcap_proc,
                       "pkt_pcap_tot",stats.pkt_pcap_tot,"pkt_pcap_drop",stats.pkt_pcap_drop,"pkt_pcap_dropif",stats.pkt_pcap_dropif);
}

static PyMethodDef pktman_methods[] =
{
  { "debugmode", (PyCFunction)pktman_debugmode, METH_VARARGS, NULL},
  { "getdev", (PyCFunction)pktman_getdev, METH_VARARGS, NULL},
  { "initialize", (PyCFunction)pktman_initialize, METH_VARARGS, NULL},
  { "setfilter", (PyCFunction)pktman_setfilter, METH_VARARGS, NULL},
  { "push", (PyCFunction)pktman_push, METH_VARARGS, NULL},
  { "pull", (PyCFunction)pktman_pull, METH_VARARGS, NULL},
  { "close", (PyCFunction)pktman_close, METH_NOARGS, NULL},
  { "getstat", (PyCFunction)pktman_getstat, METH_NOARGS, NULL},
  { NULL, NULL, 0, NULL }
};

void initpktman(void)
{
  Py_InitModule("pktman", pktman_methods);
}
