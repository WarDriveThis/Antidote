Counter Surveillance application - electronic identifier collection and transmission device

Overview

Collects local, active electronic identifiers (MAC, UUID, SSID,…) and re-transmits the pool in a manner that does not interfere with legitimate communications in any way but identifies the Antidote device with those identifiers to potential surveillance collection units nearby resulting in obfuscation of the movements of the devices with the collected identifiers. Operation generates data within the surveillance back-end system that render the data less usable for searches violating the 4th amendment. Active privacy protection for the surrounding environment (with volume).
More non-technical application description is available in README-MORE.md

Hardware Options

RaspPi Zero; USB Hat; 2x Panda PAU0A; Laird nRF52840; Seeed ESP32-S3; Buzzer; NeoPixel; external 2.4 antenna; full 3 watt power supply

Currently built for Raspberry PI Zero 2 W  with compatible connected additional radios. Note that the current implementation is a bit over-kill for the purposes of functional demonstration and uses several radios each dedicated to a single identifier and a single in or out transmission mode. 2@ Panda PAU0A and 1@ Laird 451-0004 nRF52840 are surely more expensive than required, but provided the necessary capability for the PoC. The entire BLE capability can be run on a single Seeed without the Rasp Pi, but operation with the Pi allows more broad collection and adds wifi and other identifier collection and transmission.
Hardware, OS and software choices have been made to assure access to the lower level capabilities to practically transmit varying identifiers. Note that the design attempts to remain true to the intent of BLE and WiFi privacy features and standards, it simply uses those same rolling and change-capable features to become a dynamic source of identifier data in the spirit of privacy that was intentionally built into the standards themselves.

Quick Start

Documentation contains all information required to build and flash the device. Fully operational as developed. Built as an Open Source proof of concept using Claude. Claude now declines to participate in further development, so users are welcomed to modify and advance the code and deployment platform as they like.
All configuration flags available through included on-board user interface. Initial setup using the UI is required to activate outbound transmission, but once set, the system will return to that user configured mode on restart. 

Features

Reads nearby electronic device identifiers
Stores acquired identifiers in a local pool
Randomly adjusts the perceived Antidote device identity to that of the pool identifier and retransmits for the retention period and duration configured on the user interface. 
User configurable capabilities and monitoring options, but can operate without user intervention once configured.
Typical use is simply to install and allow the device to collect legitimate, locally active reads, then allow those strings to be read at additional times and locations effectively blurring the data and denying the data user the ability to reliably perform broad or associative searches since many reads will appear in places the legitimate device was not.
Neopixel shows inhale and exhale activity as well as status of identifier transmission between the Pi and Seeed components.

License
GPLv3

Again, it is the author’s hope that these concepts will be extended and simplified to allow broad deployment. The intent was to present the ideas, demonstrate the practical implementation and share the results. The code is not perfect by any means, and the implementation is relatively crude, but again, it is fully operational and deploy able as implemented. Documentation has been provided in the GitHub repository which includes construction and deployment steps. 

Disclaimer – 

While the author believes the implementation and operation to be completely legal and within a US civilian’s rights to operate, exposure to civil and criminal liability for construction, deployment and operation of the devices described here is entirely at the risk of the operator. All are welcomed to use, modify and distribute the code and documentation associated with the projects without license or fee as long as the modifications remain open source in the public domain. 
This tool is intended for security research, privacy auditing, and educational purposes. Always comply with local laws regarding wireless scanning and signal interception. The authors are not responsible for misuse.

Antidote is distributed under the GNU General Public License version 3.
See the file LICENSE for details.

This file is part of Antidote. Antidote is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>. 
