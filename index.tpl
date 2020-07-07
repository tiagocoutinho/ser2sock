<!doctype html>
<html>
  <head>
    <title>ser2sock - {{hostname}}</title>
    <meta name="description" content="ser2sock web config page">
    <style>
    table.main {
      border: 0px;
      width: 80%;
    }
    table.main th {
      background-color: #DDDDDD;
    }
    </style>
  </head>
  <body>
    <h1>ser2sock - {{hostname}}</h1>
    <form>
    <table class="main">
      <tr>
        <th colspan="5">serial</th>
	<th colspan="1">tcp</th>
	<th rowspan="2">clients</th>
      </tr>
      <tr>
	<th>address</th>
	<th>baudrate</th>
	<th>byte size</th>
	<th>parity</th>
	<th>stop bits</th>
	<th>address</th>
      </tr>
      % for idx, bridge in enumerate(server.bridges):
      % serial, tcp = bridge.config['serial'], bridge.config['tcp']
      % baudrate = serial.get('baudrate', 9600)
      % bytesize = serial.get('bytesize', 8)
      % parity = serial.get('parity', 'N')
      % stopbits = serial.get('stopbits', 1)
      <tr>
        <td><input type="text" value="{{ serial['address'] }}" /></td>
	<td>
	  <select id="baudrate-{{idx}}">
	    % for br in baudrates:
	    <option {{ "selected" if br == baudrate else "" }}>{{br}}</option>
	    % end
	  </select>
	</td>
        <td>
	  <select  id="bytesize-{{idx}}">
	    % for bs in [6, 7, 8]:
	    <option {{ "selected" if bs == bytesize else ""}}>{{bs}}</option>
	    % end
	  </select>
	</td>
	<td>
	  <select id="parity-{{idx}}">
	    % for par in ['N', 'O', 'E']:
	    <option {{ "selected" if par == parity else ""}}>{{par}}</option>
	    % end
	  </select>
	</td>
	<td>
	  <select id="stopbits-{{idx}}">
	    % for sb in [1, 1.5, 2]:
	    <option {{ "selected" if sb == stopbits else ""}}>{{sb}}</option>
	    % end
	  </select>
	</td>
	<td><input type="text" value="{{ tcp['address'] }}" /></td>
	<td>
	  % if bridge.client:
	  {{ '{}:{}'.format(*bridge.client.getpeername()) }}
	  <!-- <button>close</button> -->
	  % end
	</td>
      </tr>
      % end
    </table>
    </form>
  </body>
</html>
