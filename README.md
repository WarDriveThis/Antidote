# Antidote
Counter Surveillance application - electronic identifier collection countermeasure

Surveillance systems are expanding their collection of electronic identifiers to map patterns of life and identify common devices at multiple locations in an effort to identify individuals by their movements rather than identifying suspects and gathering legal or warranted evidence based on probable cause. It is the author’s contention that this is a 4th Amendment issue and that public counter-measures are required to deny the violation.

Proposed approach

Flood the zone – Make Surveillance system’s strengths their weakness by using their broad surveillance collection intake points to make the entire resulting data set less reliable. 

Consider, if you will, the bowler hat scene in the Thomas Crown Affair. By presenting duplicated identifiers, the surveillance system’s utility is manipulated and breaks down.
If a device is identified in 10 places at the same time, it would call into question the utility and results across the entire system. 

**So what if you took that a step further and built something that displayed a series of legitimate, locally active electronic device identifiers, every second, in front of collection sites all across an area?**

**Meet Antidote – Simple Counter-Electronic-Surveillance-data technology.**

Rationale - 

Law Enforcement will not differentiate on their own between searches for specific suspects and 4th amendment violation dragnet searches until the later is made difficult. 

Approach - 

There is a practical method to influence the data such that legitimate, warranted searches for specific plates or suspects are unimpeded, while disabling searches seeking to identify life patterns, searches attempting to determine associations and searches broadly targeting all identifiers (plates or surveillance targets) at multiple locations/times. The goal is to complicate searches, for example, for individuals involved in multiple protests. All you have to do is feed them data that blurs their results.

Practical demonstration -

Two applications have been released today as open-source projects that implement this method. 
They have been developed using Claude, though Claude now declines to work on them any  further, sighting Sonnet 5 guard-rails. These are intended to be proofs-of-concept, though they are both fully functional. It is the author’s hope that the public anti-surveillance movement will embrace and refine them. Hopefully the broad group can find ways to simplify the implementations and reduce the cost of building functional units.
Both applications are believed by the author to be legal to develop and to operate. They are both based on technical precedents including the BLE standard privacy recommendations, built-in capabilities for MAC rolling, as well as electronic license plate legality and legal precedent for freedom of speech on vehicle displays.
The basic concept uses mass surveillance reliance on collecting identifiers (license plates, MAC addresses, SSIDs, UUIDs etc.) using their own hardware and methods and pooling those with date, time and location. The method simply feeds additional, plausible data into those channels.
By collecting and repeating, or repeatedly rebroadcasting, the identifier components of communications in a manner matching the most likely captured segments, without interfering with normal communications, collectors can be fed the identifiers of legitimate, locally recent devices over an artificial period. Over time, this generates a data blur that robs the data set of the ability to accurately coordinate mass data search. A law enforcement officer with a legitimate need to identify reads of a specific device would then need to acquire a warrant to appropriately locate the device. It is worth noting that random data would not be effective in generating this blur. To be effective, the system must actively collect identifiers and repeat their collection in different locations and times.
The applications

**CALiPeR** – a counter-ALPR application and hardware set consisting of a camera; Raspberry PI 4 B; e-Paper display; 850 Nanometer LED Strip; 850 Nanometer transparent, visible light blocking plastic cover for the display. The resulting system reads surrounding license plate text, stores them in a local cache, or pool, for configurable duration, and plays those plates back 1 per second on the e-paper display. The display is not visible to human observers because of the cover which blocks visible light, but is clearly visible and readable to ALPR cameras which use infrared illumination (~720-880 nanometer). The result is a feed of data into the ALPR database that is only distinguishable from other data by human observation, resulting in the reduction in utility of the data for broad or correlative searches. The device can be constructed for ~$150 US. The highest cost component is the e-paper display. Later implementations may use recycled displays or some less expensive, but ALPR readable alternative. The system has been tested on some ALPR cameras, but not Flock since it would require access to the data back-end. The author recommends an early test and FOIA request for a sample plate to assure the readability for Flock specifically.

**Antidote** – Expanding the CALiPeR concept to electronic surveillance, the system is comprised of a Raspberry Pi Zero 2 W, several Bluetooth and WiFi USB radios and a Seeed microcontroller. The microcontroller component is capable of independent operation for the BLE component (ala Colonel Panic Unified Blue) but can also act in an integrated fashion with the Raspberry Pi. In the extended version the Raspberry Pi’s dedicated Bluetooth data collection process streams data to the Seeed which handles outbound Bluetooth communications. The system performs 2 concurrent functions – Inhale - in which it gathers local electronic surveillance identifiers; and Exhale which transmits the signal components used by electronic surveillance devices for collection. The result is, again, the injection of data into the electronic surveillance collection flow that blurs or repeats data from devices that are actually no longer, or never were, in the collector’s range. The electronic surveillance system is thereby no longer able to reliably report the presence or absence of a specific device or devices at a given date, time, location rendering the collection unusable. The full spectrum device can be constructed for ~$65 US though the BLE only Seeed module can be built for less than $15. This implementation uses longer than necessary range and distinct radios for collection and transmission on each target technology, which is overkill and doubled the cost, but resulted in a very effective proof of concept. The system is designed not to jam, or in any way interfere with, ongoing legitimate electronic communications since the fragments transmitted are discarded by legitimate recipients, but are collected by electronic surveillance devices. 
Note that the Seeed component should theoretically be compatible with the OUI-SPY Unified Blue though no attempt at that integration has been made at the time of publication.

Again, it is the author’s hope that these concepts will be extended and simplified to allow broad deployment. The intent was to present the ideas, demonstrate the practical implementation and share the results. The code is not perfect by any means, and the implementation is relatively crude, but again, it is fully operational and deploy able as implemented. Documentation has been provided in the GitHub repository which includes construction and deployment steps. 

Disclaimer – 

While the author believes the implementation and operation to be completely legal and within a US civilian’s rights to operate, exposure to civil and criminal liability for construction, deployment and operation of the devices described here is entirely at the risk of the operator. All are welcomed to use, modify and distribute the code and documentation associated with the projects without license or fee as long as the modifications remain open source in the public domain. 
This tool is intended for security research, privacy auditing, and educational purposes. Always comply with local laws regarding wireless scanning and signal interception. The authors are not responsible for misuse.

Antidote is distributed under the GNU General Public License version 3.
See the file LICENSE for details.

This file is part of Antidote. Antidote is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>. 
