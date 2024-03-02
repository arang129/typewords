"""A minimal example server to run with jupyter-server-proxy
"""
import argparse
import socket
import sys
from copy import copy
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

__version__ = '0.41'

# This is the entry point for jupyter-server-proxy . The packaging metadata
# tells it about this function. For details, see:
# https://jupyter-server-proxy.readthedocs.io/en/latest/server-process.html
def setup_hello():
    # Using a Unix socket prevents other users on a multi-user system from accessing
    # our server. The alternative is a TCP socket ('-p', '{port}').
    return {
        'command': [sys.executable, '-m', 'hello_jupyter_proxy', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/yunlab.svg',
            'title': 'YunLab',
        },
    }

# Define a web application to proxy.
# You would normally do this with a web framework like tornado or Flask, or run
# something else outside of Python.
# This example uses Python's low-level http.server, to minimise dependencies.
class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        server_addr = self.server.server_address
        if isinstance(server_addr, tuple):
            server_addr = "{}:{}".format(*server_addr)

        try:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(TEMPLATE.format(
                path=self.path, headers=self._headers_hide_cookie(),
                server_address=server_addr,
            ).encode('utf-8'))
        except BrokenPipeError:
            # Connection closed without the client reading the whole response.
            # Not a problem for the server.
            pass

    def address_string(self):
        # Overridden to fix logging when serving on Unix socket
        if isinstance(self.client_address, str):
            return self.client_address  # Unix sock
        return super().address_string()

    def _headers_hide_cookie(self):
        # Not sure if there's any security risk in showing the Cookie value,
        # but better safe than sorry. You can inspect cookie values in the
        # browser.
        res = copy(self.headers)
        if 'Cookie' in self.headers:
            del res['Cookie']
            res['Cookie'] = '(hidden)'
        return res


TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
	<title>Website in YunLab</title>
</head>
 
<body>

<!-- Start Header -->
<table border="0" width="100%" cellpadding="0" cellspacing="0" bgcolor="#f3971b">
  <tr>
  	 <td>
  	 	<table border="0" width="85%" cellpadding="15" cellspacing="0" align="center">
           <tr>
           	   <td>
           	   	  <font face="arial" color="black" size="5">
           	       <strong>YunLab</strong>
           	      </font>
           	   </td>
           	   <td width="30%">&nbsp;</td>
           	   <td><a href="#home">
           	   	  <font face="arial" color="#ffffff" size="3">
           	       Home
           	     </font></a>
           	   </td>
           	   <td><a href="#bookmarks">
           	   	 <font face="arial" color="#ffffff" size="3">
           	      Bookmarks
           	  </font></a>
           	  </td>
			  <td><a href="#tutorials">
				  <font face="arial" color="#ffffff" size="3">
				   Tutorials
				  </font></a>
			  </td>
			  <td><a href="#about">
				<font face="arial" color="#ffffff" size="3">
			    About
			    </font></a>
		      </td>
			  <td><a href="#contact">
				<font face="arial" color="#ffffff" size="3">
			    Contact
			    </font></a>
		      </td>

           </tr>
  	 	</table>
  	 </td>
  </tr>
</table>
<!-- End Header -->


<!-- Start Home -->
<table border="0" id="home" width="100%" cellpadding="0" cellspacing="0" bgcolor="#292929">
  <tr>
  	 <td>
  	 	<table border="0" width="85%" cellpadding="15" cellspacing="0" align="center">
           <tr>
           	   <td align="center" valign="middle" height="300">
           	   	 <h3>
           	   	 	<marquee behavior="alternate" direction="left" scrollamount="2">
           	   	 	<font face="arial" color="#ffffff" size="6">
					Hello, World!
           	   	    </font>
           	   	   </marquee>
           	   	</h3>
           	   	 <h1>
           	   	 	<marquee behavior="alternate" direction="right" scrollamount="2">
           	   	 	<font face="arial" color="#f3971b" size="7">
					Coding in the YunLab
           	   	    </font>
           	   	</marquee>
           	   	</h1>
           	   </td>
           </tr>
        </table>
      </td>
    </tr>
 </table>
<!-- End Home -->


<!-- Start Bookmarks -->
<table border="0" id="bookmarks" width="100%" cellpadding="0" cellspacing="0" bgcolor="#292929">
  <tr>
  	 <td>
  	 	<table border="0" width="85%" cellpadding="15" cellspacing="0" align="center">
  	 	<!-- Heading Start-->
          <tr>
           	  <td height="160" align="center" valign="middle" colspan="3">
           	  	 <font face="arial" size="6" color=" #f3971b">
           	  	   Bookmarks
           	  	</font>
           	  	<hr width="70" color="#f3971b">
           	  </td>
          </tr>
        <!-- Heading  End-->
         <tr>
         	<td width="33.33%" valign="top">
         	  <table border="0" width="100%" cellpadding="15" cellspacing="0" align="center" bgcolor="#353535">
         	  	<tr>
         	  		<td>
         	  			<font face="arial" size="5" color="#ffffff">
						Tutorials
         	  		   </font>
         	  		   <br/><br/>
						  <a href="https://memos.yunlab.synology.me/" target="_blank">
							<img src="https://i.imgur.com/QxuVTyY.png" width="100" alt="Tutorials" title="Tutorials">
						  </a>
         	  		</td>
         	  	</tr>
         	  </table>	
         	</td>
         	
         	<td width="33.33%" valign="top">
				<table border="0" width="100%" cellpadding="15" cellspacing="0" align="center" bgcolor="#353535">
					<tr>
						<td>
							<font face="arial" size="5" color="#ffffff">
							Derivatives
						    </font>
						   <br/><br/>
						   <a href="https://finance.yunlab.synology.me/" target="_blank">
							<img src="https://upload.wikimedia.org/wikipedia/commons/d/d7/Philippine-stock-market-board.jpg" width="100" alt="Derivatives" title="Derivatives">
						  </a>
						</td>
					</tr>
				</table>	
			  </td>
			  <td width="33.33%" valign="top">
				<table border="0" width="100%" cellpadding="15" cellspacing="0" align="center" bgcolor="#353535">
					<tr>
						<td>
							<font face="arial" size="5" color="#ffffff">
							MySQL
						   </font>
						   <br/><br/>
						   <a href="https://data.yunlab.synology.me/" target="_blank">
							<img src="https://upload.wikimedia.org/wikipedia/zh/thumb/6/62/MySQL.svg/1200px-MySQL.svg.png" width="150" alt="MySQL" title="MySQL">
						  </a>
						</td>
					</tr>
				</table>	
			  </td>
         </tr>
        <tr>

         	<td width="33.33%" valign="top">
         	  <table border="0" width="100%" cellpadding="15" cellspacing="0" align="center" bgcolor="#353535">
         	  	<tr>
         	  		<td>
         	  			<font face="arial" size="5" color="#ffffff">
					    ChatGPT
         	  		   </font>
         	  		   <br/><br/>
						  <a href="https://gpt.yunlab.synology.me/" target="_blank">
							<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/ChatGPT_logo.svg/640px-ChatGPT_logo.svg.png" width="100" alt="ChatGPT" title="ChatGPT">
						  </a>
         	  		</td>
         	  	</tr>
         	  </table>	
         	</td>
         	
         	<td width="33.33%" valign="top">
				<table border="0" width="100%" cellpadding="15" cellspacing="0" align="center" bgcolor="#353535">
					<tr>
						<td>
							<font face="arial" size="5" color="#ffffff">
							SAS Studio
						   </font>
						   <br/><br/>
						   <a href="https://sas.yunlab.synology.me/SASStudio/" target="_blank">
							<img src="https://i.pinimg.com/originals/73/96/b8/7396b8543078228985df506d122df2e7.png" width="100" alt="SAS Studio" title="SAS Studio">
						  </a>
						</td>
					</tr>
				</table>	
			  </td>

			  <td width="33.33%" valign="top">
				<table border="0" width="100%" cellpadding="15" cellspacing="0" align="center" bgcolor="#353535">
					<tr>
						<td>
							<font face="arial" size="5" color="#ffffff">
							Blog
						   </font>
						   <br/><br/>
						   <a href="https://blog.yunlab.synology.me/" target="_blank">
							<img src="https://i.imgur.com/lEcnJPU.png" width="100" alt="Blog" title="Blog">
						  </a>
						</td>
					</tr>
				</table>	
			  </td>
         	  	</tr>
         	  </table>	
         	</td>

         </tr>
        <!-- section padding bottom -->
           <tr>
           	  <td height="60" colspan="3">
                 
           	  </td>
           </tr>
          <!-- section padding bottom End-->
       </table>
     </td>
   </tr>
</table>
<!-- End Bookmarks -->

<!-- Start Tutorials -->
<table border="0" id="tutorials" width="100%" cellpadding="0" cellspacing="0" bgcolor="#292929">
	<tr>
		 <td>
			 <table border="0" width="100%" cellpadding="15" cellspacing="0" align="center">
			 <!-- Heading Start-->
			<tr>
				   <td height="160" align="center" valign="middle" colspan="3">
						<font face="arial" size="6" color=" #f3971b">
						  Tutorials
					   </font>
					   <hr width="70" color="#f3971b">
				   </td>
			</tr>
		  <!-- Heading  End-->
		  <tr>
			<td width="100%" valign="top">
				<table border="0" width="100%" cellpadding="0" cellspacing="0" align="center">
					  <tr>
						   <td align="center" valign="middle" height="120">
							<iframe src="https://memos.yunlab.synology.me/explore" width="1200px" height="1000px" frameborder="0"></iframe>
						   </td>
					  </tr>
				</table>  
		  </td>
		  </tr>
		  <!-- section padding bottom -->
			 <tr>
				   <td height="60" colspan="3">
				   
				   </td>
			 </tr>
			<!-- section padding bottom End-->
			 </table>
		 </td>
	</tr>
  </table>
  <!-- End Tutorials -->
  

<!-- Start About -->
<table border="0" id="about" width="100%" cellpadding="0" cellspacing="0" bgcolor="#353535">
	<tr>
		 <td>
			 <table border="0" width="85%" cellpadding="15" cellspacing="0" align="center">
				 <!-- Heading Start-->
			 <tr>
				   <td height="160" align="center" valign="middle" colspan="2">
						<font face="arial" size="6" color=" #f3971b">
						  About
					   </font>
					   <hr width="70" color="#f3971b">
				   </td>
			 </tr>
			 <!-- Heading  End-->
			 <tr>
					<td width="35%">
						  <img src="https://umf.yuntech.edu.tw/upload/teacher_20221227101549.jpg" width="100%" alt="me" />
					</td>
					<td width="65%" valign="top">
						  <table border="0" width="100%" cellpadding="0" cellspacing="0" align="center">
								<tr>
									 <td height="40">
										 <font face="arial" size="4" color=" #ffffff">
										 Hi, I'm Wen-Rang Liu
										</font>
									 </td>
								</tr>
								<tr>
									<td>
										<p>
											<font face="arial" size="3" color="#c2c0c3">
												Wen-Rang Liu is an Assistant Professor in the Department of Finance at the National Yunlin University of Science and Technology. He received his Ph.D. and Master’s degrees in Finance from National Taiwan University and his Bachelor’s degree from National Tsing Hua University. Prior to his current position, Wen-Rang undertook postdoctoral research at the Hong Kong Polytechnic University. He is an SGS-certified lead auditor for ISO 14064-2:2019 and has completed the PAS 2060:2014 training course by SGS. He has participated in collaborative projects between industry and academia, specifically in the field of carbon inventory. His academic research interests lie in empirical asset pricing, derivatives markets, and investment strategies.
											</font>
										</p>
										<hr noshade>
										<br/>
									</td>
								</tr>
						  </table>  
					</td>
			 </tr>
			<!-- section padding bottom -->
			 <tr>
				   <td height="60" colspan="2">
				   
				   </td>
			 </tr>
			<!-- section padding bottom End-->
		  </table>
		</td>
	 </tr>
  </table>
  <!-- End About -->
  
<!-- Start Contact -->
<table border="0" id="contact" width="100%" cellpadding="0" cellspacing="0" bgcolor="#292929">
	<tr>
		 <td>
			 <table border="0" width="100%" cellpadding="15" cellspacing="0" align="center">
			 <!-- Heading Start-->
			<tr>
				   <td height="160" align="center" valign="middle" colspan="3">
						<font face="arial" size="6" color=" #f3971b">
						  Contact
					   </font>
					   <hr width="70" color="#f3971b">
				   </td>
			</tr>
		  <!-- Heading  End-->
		  <tr>
			<td height="40" align="center">
				<font face="arial" size="4" color=" #ffffff">
				To contact me, please click the button in the lower right corner to open the chat window.
			   </font>
			</td>
	   </tr>
		  </tr>
		  <!-- section padding bottom -->
			 <tr>
				   <td height="60" colspan="3">
				   
				   </td>
			 </tr>
			<!-- section padding bottom End-->
			 </table>
		 </td>
	</tr>
  </table>
  <!-- End Contact -->


<!-- 将以下代码片段放于你的网页内，建议放于 body 底部 -->
<script
  data-host-id="1"
  data-auto-reg="true"
  data-login-token=""
  data-close-width="52"
  data-close-height="52"
  data-open-width="380"
  data-open-height="680"
  data-position="right"
  data-welcome="歡迎留言"
  src="https://chat.yunlab.synology.me/widget.js"
  async
></script>

</body>
</html>
"""

class HTTPUnixServer(HTTPServer):
    address_family = socket.AF_UNIX

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--port')
    ap.add_argument('-u', '--unix-socket')
    args = ap.parse_args()

    if args.unix_socket:
        print("Unix server at", repr(args.unix_socket))
        Path(args.unix_socket).unlink(missing_ok=True)
        httpd = HTTPUnixServer(args.unix_socket, RequestHandler)
    else:
        # 127.0.0.1 = localhost: only accept connections from the same machine
        print("TCP server on port", int(args.port))
        httpd = HTTPServer(('127.0.0.1', int(args.port)), RequestHandler)
    print("Launching example HTTP server")
    httpd.serve_forever()

if __name__ == '__main__':
    main()
