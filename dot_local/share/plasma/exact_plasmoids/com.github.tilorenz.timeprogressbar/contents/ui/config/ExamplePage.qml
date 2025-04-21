//import QtQuick
//import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami

////import "."

//Kirigami.ApplicationWindow {
    //id: root
 
    //width: 500
    //height: 400
 
    //pageStack.initialPage: mainPageComponent
    //Component {
        //id: mainPageComponent
        //Kirigami.ScrollablePage {
            //id: page
            //title: "Hello"
            ////Page contents...
            //Rectangle {
                //anchors.fill: parent
                //color: "lightblue"
            //}
			////TimeField{
				////show24: false
				////hours: 12
				////minutes: 34
			////}
			//QQC.Button {
				//id: ihatethis
				//icon.name: "expand-symbolic"
				//checkable: true
				//QQC.ToolTip { text: "Bold text" }
				//Accessible.name: QQC.ToolTip.text
				//background: Rectangle {
					//implicitWidth: 30
					//implicitHeight: 30
					//color: ihatethis.checked ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
				//}
			//}
		//}
    //}
//}

import QtQuick
import QtQuick.Controls 
//QQC.Button {
	//icon.name: "expand-symbolic"
	//text: "test"
	//background: Rectangle {
		//implicitWidth: 80
		//implicitHeight: 30
		//color: "black"
	//}
//}

	Rectangle {
		z: 99
		width: 200
		height: 300
		color: Kirigami.Theme.backgroundColor
		RangeSlider {
			enabled: true
			z: 100
			y: 0
		}
		RangeSlider {
			enabled: false
			z: 100
			y: 20
		}
		Slider {
			enabled: true
			z: 100
			y: 50
			value: 0.5
		}
		Slider {
			enabled: false
			z: 100
			y: 70
			value: 0.5
		}
	}

