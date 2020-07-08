<!doctype html>
<html>
  <head>
    <title>ser2sock - {{hostname}}</title>
    <meta name="description" content="ser2sock web config page">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <!--    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.0/css/bootstrap.min.css"> -->
    <link rel="stylesheet" href="/static/bootstrap.min.css">
  </head>
  <body>
    <div class="container-fluid">
      <div class="card">
	<div class="card-header text-center">ser2sock - {{hostname}}</div>
	<div class="card-body">
	  <form action="/" method="post" class="form-group">
	    <table class="table table-striped table-sm">
	      <thead class="thead-light">
		<tr>
		  <th rowspan="2" scope="col">#</th>
		  <th colspan="5" scope="col">serial</th>
		  <th colspan="1" scope="col">tcp</th>
		  <th colspan="3" scope="col">client</th>
		  <th colspan="2" scope="col">traffic</th>
		</tr>
		<tr>
		  <th scope="col">port</th>
		  <th scope="col">baudrate</th>
		  <th scope="col">byte size</th>
		  <th scope="col">parity</th>
		  <th scope="col">stop bits</th>
		  <th scope="col">address</th>
		  <th scope="col">origin</th>
		  <th scope="col">last connection</th>
		  <th scope="col">history</th>
		  <th scope="col">tcp->sl</th>
		  <th scope="col">sl->tcp</th>
		</tr>
	      </thead>
	      % for idx, bridge in enumerate(server.bridges):
	      % serial, tcp = bridge.config['serial'], bridge.config['tcp']
	      % baudrate = serial['baudrate']
	      % bytesize = serial['bytesize']
	      % parity = serial['parity']
	      % stopbits = serial['stopbits']
	      <tr>
		<th scope="row">{{idx}}</th>
		<td>
		  <input type="text" name="serial-port-{{idx}}"
			 value="{{ serial['port'] }}"
			 class="form-control form-control-sm"/>
		</td>
		<td>
		  <select name="serial-baudrate-{{idx}}"
			  class="form-control form-control-sm">
		    % for br in baudrates:
		    <option {{ "selected" if br == baudrate else "" }}>{{br}}</option>
		    % end
		  </select>
		</td>
		<td>
		  <select  name="serial-bytesize-{{idx}}"
			   class="form-control form-control-sm">
		    % for bs in [6, 7, 8]:
		    <option {{ "selected" if bs == bytesize else ""}}>{{bs}}</option>
		    % end
		  </select>
		</td>
		<td>
		  <select name="serial-parity-{{idx}}"
			  class="form-control form-control-sm">
		    % for par in ['N', 'O', 'E']:
		    <option {{ "selected" if par == parity else ""}}>{{par}}</option>
		    % end
		  </select>
		</td>
		<td>
		  <select name="serial-stopbits-{{idx}}"
			  class="form-control form-control-sm">
		    % for sb in [1, 1.5, 2]:
		    <option {{ "selected" if sb == stopbits else ""}}>{{sb}}</option>
		    % end
		  </select>
		</td>
		<td>
		  <input name="tcp-address-{{idx}}" type="text"
			 value="{{ tcp['address'] }}"
			 class="form-control form-control-sm" />
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
	    <button type="submit" class="btn btn-primary">Apply</button>
	  </form>
	</div>
      </div>
    </div>
  </body>
</html>
