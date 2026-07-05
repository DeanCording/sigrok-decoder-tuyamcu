import sigrokdecode as srd


CMD_NAMES = {
    0x00: 'Heartbeat',
    0x01: 'Query Product Info',
    0x02: 'Query Working Mode',
    0x03: 'Report Network Status',
    0x04: 'Reset WiFi',
    0x05: 'Reset WiFi + Pairing',
    0x06: 'Send Command',
    0x07: 'Report Status Async',
    0x08: 'Query Status',
    0x0C: 'Get GMT',
    0x0F: 'Get Memory',
    0x1C: 'Get Local Time',
    0x22: 'Report Status Sync',
    0x24: 'WiFi Signal',
    0x25: 'Disable Heartbeat',
    0x2A: 'Serial Pairing',
    0x2B: 'Request Network Status',
    0x2D: 'Get MAC',
    0x34: 'Report Status Record',
}

DP_TYPES = {
    0x00: 'raw',
    0x01: 'bool',
    0x02: 'value',
    0x03: 'string',
    0x04: 'enum',
    0x05: 'bitmap',
}


class Decoder(srd.Decoder):
    api_version = 3
    id = 'tuyamcu'
    name = 'Tuya MCU'
    longname = 'Tuya Serial Communication Protocol'
    desc = 'Tuya Serial Communication Protocol over UART'
    license = 'gplv3+'
    inputs = ['uart']
    outputs = ['tuyamcu']
    tags = ['Tuya', 'Embedded']

    annotations = (
        ('framerx', 'Frame RX'),
        ('framedatarx', 'Frame Data RX'),
        ('dprx', 'DP RX'),
        ('frametx', 'Frame TX'),
        ('framedatatx', 'Frame Data TX'),
        ('dptx', 'DP TX'),
    )

    annotation_rows = (
        ('frames', 'Frames RX', (0,)),
        ('frame', 'Frame RX', (1,)),
        ('dps', 'DPs RX', (2,)),
        ('frames', 'Frames TX', (3,)),
        ('frame', 'Frame TX', (4,)),
        ('dps', 'DPs TX', (5,)),
    )


    def __init__(self):
        self.reset()


    def reset(self):
        self.state = ["WAIT","WAIT"]
        self.header = [0,0]
        self.counter = [0,0]
        self.buf = [[],[]]

        self.data_buf = [[],[]]

        self.ss = [None,None]
        self.ss_frame = [None,None]
        self.ss_data = [None,None]

        self.frame_version = [0,0]
        self.frame_command = [0,0]
        self.frame_length = [0,0]
        self.frame_data = [[],[]]

        self.data_type = [0,0]
        self.data_length = [0,0]
        self.data_data = [[],[]]


    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
    

    def decode_value(self, data: list, type: int) -> str:
        # raw
        if type == 0x00:
            return " ".join(f"{b:02X}" for b in data)
        # bool
        elif type == 0x01:
            return "ON" if data[0] else "OFF"
        # value (int, big-endian)
        elif type == 0x02:
            val = 0
            for b in data:
                val = (val << 8) | b
            return str(val)
        # string
        elif type == 0x03:
            return bytes(data).decode("utf-8", errors="replace")
        # enum
        elif type == 0x04:
            return str(data[0])
        # bitmap
        elif type == 0x05:
            val = 0
            for b in data:
                val = (val << 8) | b
            bits_cnt = len(data) * 8
            bin_str = f"{val:0{bits_cnt}b}"
            grouped = " ".join(bin_str[i:i+4] for i in range(0, len(bin_str), 4))
            return f"0b{grouped}"
        # other types
        else:
            return " ".join(f"{b:02X}" for b in data)
    

    def decode_data(self, rxtx: int, data: tuple):
        state = "DPID"
        counter = 0
        length = 0
        buffer = []
        ss_data = None
        data_type = 0

        for ss, es, d in data:
            if state == "DPID":
                # add marker
                self.put(
                    ss, es,
                    self.out_ann,
                    [2+3*rxtx, [f"DPID: {d}"]]
                )
                # reset stuff
                counter = 0
                state = "TYPE"
            
            elif state == "TYPE":
                # add marker
                data_type = d
                type_name = DP_TYPES.get(d, f"Unknown")
                self.put(
                    ss, es,
                    self.out_ann,
                    [2+3*rxtx, [f"Type: {type_name}"]]
                )
                # reset stuff
                counter = 0
                state = "LENGTH"
            
            elif state == "LENGTH":
                if counter == 1:
                    ss_data = ss
                length = (length << 8) | (d & 0xFF)
                if counter >= 2:
                    # add marker
                    self.put(
                        ss_data, es,
                        self.out_ann,
                        [2+3*rxtx, [f"Length: {length}"]]
                    )
                    # reset stuff
                    counter = 0
                    buffer = []
                    state = "DATA"
            
            elif state == "DATA":
                if counter == 1:
                    ss_data = ss
                buffer.append(d)
                if counter >= length:
                    # add marker
                    value = self.decode_value(buffer, data_type)
                    self.put(
                        ss_data, es,
                        self.out_ann,
                        [2+3*rxtx, [f"Value: {value}"]]
                    )
                    # reset stuff
                    counter = 0
                    state = "ERROR"

            counter += 1


    def decode_product(self, rxtx: int, data: tuple):
        decoded_str = ""
        ss_data = None
        es_data = None
        for ss, es, d in data:
            if ss_data is None:
                ss_data = ss
            es_data = es
            # decode data
            decoded_str += chr(d)
        self.put(
            ss_data, es_data,
            self.out_ann,
            [2+3*rxtx, [f"Data: {decoded_str}"]]
        )


    def decode(self, ss, es, data):
        ptype, rxtx, pdata = data

        if ptype != "DATA":
            return

        ch = int(rxtx) # 0:rx 1:tx
        byte = pdata[0]

        if self.state[ch] == "WAIT":
            # find header
            if byte == 0x55:
                self.ss[ch] = ss
                self.ss_frame[ch] = ss
            self.header[ch] = (self.header[ch] << 8) | (byte & 0xFF)
            if self.header[ch] & 0xFFFF == 0x55AA:
                self.counter[ch] = 0
                self.state[ch] = "VERSION"
                # add marker
                self.put(
                    self.ss[ch], es,
                    self.out_ann,
                    [1+3*ch, ["Header"]]
                )
        
        elif self.state[ch] == "VERSION":
            # parse version
            self.frame_version[ch] = byte
            self.counter[ch] = 0
            self.state[ch] = "COMMAND"
            # add marker
            self.put(
                ss, es,
                self.out_ann,
                [1+3*ch, [f"Version: {byte}"]]
            )
        
        elif self.state[ch] == "COMMAND":
            # parse command
            self.frame_command[ch] = byte
            self.counter[ch] = 0
            self.state[ch] = "LENGTH"
            self.frame_length[ch] = 0
            # add marker
            cmd_name = CMD_NAMES.get(byte, f"Unknown")
            self.put(
                ss, es,
                self.out_ann,
                [1+3*ch, [f"Cmd: {cmd_name}"]]
            )
        
        elif self.state[ch] == "LENGTH":
            if self.counter[ch] == 1:
                self.ss[ch] = ss
            # parse packet length
            self.frame_length[ch] = (self.frame_length[ch] << 8) | (byte & 0xFF)
            if self.counter[ch] >= 2:
                self.counter[ch] = 0
                if self.frame_length[ch] == 0:
                    self.state[ch] = "CHECKSUM"
                else:
                    self.state[ch] = "DATA"
                # add marker
                self.put(
                    self.ss[ch], es,
                    self.out_ann,
                    [1+3*ch, [f"Length: {self.frame_length[ch]}"]]
                )
        
        elif self.state[ch] == "DATA":
            if self.counter[ch] == 1:
                self.ss[ch] = ss
            self.frame_data[ch].append((ss, es, byte))
            # parse data
            if self.counter[ch] >= self.frame_length[ch]:
                self.counter[ch] = 0
                self.state[ch] = "CHECKSUM"
                # add marker
                hex_data = " ".join(f"{b:02X}" for s,e,b in self.frame_data[ch])
                self.put(
                    self.ss[ch], es,
                    self.out_ann,
                    [1+3*ch, [f"Data: {hex_data}"]]
                )
                # decode data based off command
                if self.frame_command[ch] == 0x01:
                    self.decode_product(ch, self.frame_data[ch])
                elif self.frame_command[ch] in [0x06, 0x07, 0x22, 0x34]:
                    self.decode_data(ch, self.frame_data[ch])
        
        elif self.state[ch] == "CHECKSUM":
            # add marker
            cmd_name = CMD_NAMES.get(self.frame_command[ch], f"Unknown")
            self.put(
                self.ss_frame[ch], es,
                self.out_ann,
                [0+3*ch, [f"Tuya Frame ({cmd_name})"]]
            )
            self.put(
                ss, es,
                self.out_ann,
                [1+3*ch, [f"Checksum: {byte}"]]
            )
            # reset
            self.frame_version[ch] = 0
            self.frame_command[ch] = 0
            self.frame_length[ch] = 0
            self.frame_data[ch] = []
            self.counter[ch] = 0
            self.state[ch] = "WAIT"
        
        self.counter[ch] += 1
