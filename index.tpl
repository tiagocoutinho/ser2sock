<!doctype html>
<html>
  <head>
    <title>ser2sock - {{hostname}}</title>
    <meta name="description" content="ser2sock web config page">
    <style>
    table.main {
      border: 0px;
    }
    table.main th {
      background-color: #DDDDDD;
    }
    </style>
  </head>
  <body>
    <h1>ser2sock - {{hostname}}</h1>
    <form action="/" method="post">
    <table class="main">
      <tr>
        <th colspan="5">serial</th>
	<th colspan="1">tcp</th>
	<th colspan="3">client</th>
	<th colspan="2">traffic</th>
      </tr>
      <tr>
	<th>port</th>
	<th>baudrate</th>
	<th>byte size</th>
	<th>parity</th>
	<th>stop bits</th>
	<th>address</th>
	<th>origin</>
	<th>last connection</th>
	<th>history</th>
	<th>tcp->sl</th>
	<th>sl->tcp</th>
      </tr>
      % for idx, bridge in enumerate(server.bridges):
      % serial, tcp = bridge.config['serial'], bridge.config['tcp']
      % baudrate = serial['baudrate']
      % bytesize = serial['bytesize']
      % parity = serial['parity']
      % stopbits = serial['stopbits']
      <tr>
        <td>
	  <input type="text" name="serial-port-{{idx}}"
	         value="{{ serial['port'] }}" />
	</td>
	<td>
	  <select name="serial-baudrate-{{idx}}">
	    % for br in baudrates:
	    <option {{ "selected" if br == baudrate else "" }}>{{br}}</option>
	    % end
	  </select>
	</td>
        <td>
	  <select  name="serial-bytesize-{{idx}}">
	    % for bs in [6, 7, 8]:
	    <option {{ "selected" if bs == bytesize else ""}}>{{bs}}</option>
	    % end
	  </select>
	</td>
	<td>
	  <select name="serial-parity-{{idx}}">
	    % for par in ['N', 'O', 'E']:
	    <option {{ "selected" if par == parity else ""}}>{{par}}</option>
	    % end
	  </select>
	</td>
	<td>
	  <select name="serial-stopbits-{{idx}}">
	    % for sb in [1, 1.5, 2]:
	    <option {{ "selected" if sb == stopbits else ""}}>{{sb}}</option>
	    % end
	  </select>
	</td>
	<td>
	  <input name="tcp-address-{{idx}}" type="text"
	         value="{{ tcp['address'] }}" />
	</td>
	<td align="center">
	  % if bridge.client:
	  {{ '{}:{}'.format(*bridge.client.getpeername()) }}
	  <!-- <button>close</button> -->
	  % else:
	  -
	  % end
	</td>
	<td align="center">
	  % if bridge.client_ts:
	    {{ bridge.client_ts }}
	  % else:
	  -
	  % end
	</td>
	<td> {{ bridge.client_nb }} </td>
	<td align="center">
	  % if bridge.client_bytes:
	    {{ '{:.3f} {}B'.format(*human_size(bridge.client_bytes)) }}
	  % else:
	  -
	  % end
	</td>
	<td align="center">
	  % if bridge.serial_bytes:
	    {{ '{:.3f} {}B'.format(*human_size(bridge.serial_bytes)) }}
	  % else:
	  -
	  % end
	</td>
      </tr>
      % end
    </table>
    <button type="submit">Apply</button>
    </form>
  </body>
</html>
