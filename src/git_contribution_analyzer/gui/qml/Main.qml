import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtCharts

ApplicationWindow {
    id: window
    width: 1280
    height: 820
    minimumWidth: 760
    minimumHeight: 560
    visible: true
    title: qsTr("Git Contribution Analyzer")
    color: palette.window

    property int pageIndex: 0
    property string exportRunId: gca.currentRunId
    property string exportFormat: "markdown"
    property string transientMessage: ""

    function splitValues(value) {
        return value.split(",").map(item => item.trim()).filter(item => item.length > 0)
    }

    Connections {
        target: gca
        function onNotification(message) {
            transientMessage = message
            notificationTimer.restart()
        }
    }

    Timer {
        id: notificationTimer
        interval: 3500
        onTriggered: transientMessage = ""
    }

    FolderDialog {
        id: repositoryDialog
        title: qsTr("Open Git repository")
        onAccepted: gca.openRepository(selectedFolder.toString())
    }

    FileDialog {
        id: exportDialog
        title: qsTr("Export report")
        fileMode: FileDialog.SaveFile
        nameFilters: exportFormat === "csv"
            ? [qsTr("CSV files (*.csv)")]
            : exportFormat === "json"
              ? [qsTr("JSON files (*.json)")]
              : [qsTr("Markdown files (*.md)")]
        onAccepted: gca.exportRun(exportRunId, exportFormat, selectedFile.toString(), false, false)
    }

    header: ToolBar {
        height: 58

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 12

            ToolButton {
                text: "GCA"
                font.pixelSize: 18
                font.bold: true
                onClicked: pageIndex = 0
                Accessible.name: qsTr("Open overview")
            }

            Rectangle {
                width: 1
                height: 26
                color: palette.midlight
            }

            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true

                Label {
                    text: gca.repositoryName
                    font.bold: true
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }

                Label {
                    text: gca.repositoryPath
                    visible: gca.repositoryPath.length > 0
                    color: palette.mid
                    font.pixelSize: 11
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }
            }

            RowLayout {
                visible: gca.busy
                spacing: 8

                BusyIndicator {
                    running: gca.busy
                    implicitWidth: 28
                    implicitHeight: 28
                }

                Label {
                    text: gca.taskMessage
                    elide: Text.ElideRight
                    Layout.maximumWidth: 220
                }

                Button {
                    text: qsTr("Cancel")
                    onClicked: gca.cancelTask("")
                    Accessible.name: text
                }
            }

            Button {
                text: qsTr("Sync")
                enabled: gca.workspaceInitialized && !gca.busy
                onClicked: gca.syncRepository()
                Accessible.name: text
            }

            Button {
                text: qsTr("Open")
                onClicked: repositoryDialog.open()
                Accessible.name: qsTr("Open repository")
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Pane {
            id: navigation
            Layout.preferredWidth: window.width < 900 ? 64 : 210
            Layout.fillHeight: true
            padding: 10

            ColumnLayout {
                anchors.fill: parent
                spacing: 3

                Repeater {
                    model: [
                        {label: qsTr("Overview"), shortLabel: "O"},
                        {label: qsTr("Structure"), shortLabel: "ST"},
                        {label: qsTr("Assessment"), shortLabel: "A"},
                        {label: qsTr("Trends"), shortLabel: "T"},
                        {label: qsTr("People"), shortLabel: "P"},
                        {label: qsTr("Work items"), shortLabel: "W"},
                        {label: qsTr("Runs"), shortLabel: "R"},
                        {label: qsTr("Resume"), shortLabel: "CV"},
                        {label: qsTr("Settings"), shortLabel: "S"}
                    ]

                    delegate: Button {
                        required property var modelData
                        required property int index
                        text: navigation.width < 100 ? modelData.shortLabel : modelData.label
                        flat: true
                        highlighted: pageIndex === index
                        Layout.fillWidth: true
                        Layout.preferredHeight: 42
                        onClicked: pageIndex = index
                        ToolTip.visible: hovered && navigation.width < 100
                        ToolTip.text: modelData.label
                        Accessible.name: modelData.label
                    }
                }

                Item { Layout.fillHeight: true }

                Label {
                    text: "v" + gca.appVersion
                    color: palette.mid
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }

        Rectangle {
            width: 1
            Layout.fillHeight: true
            color: palette.midlight
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    visible: gca.errorMessage.length > 0
                    color: palette.alternateBase
                    Layout.fillWidth: true
                    implicitHeight: errorRow.implicitHeight + 20

                    RowLayout {
                        id: errorRow
                        anchors.fill: parent
                        anchors.margins: 10

                        Label {
                            text: gca.errorMessage
                            color: "#b42318"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        ToolButton {
                            text: "X"
                            onClicked: gca.clearError()
                            Accessible.name: qsTr("Dismiss error")
                        }
                    }
                }

                StackLayout {
                    currentIndex: pageIndex
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    // Overview
                    ScrollView {
                        contentWidth: availableWidth

                        ColumnLayout {
                            width: parent.width
                            spacing: 22
                            anchors.margins: 28

                            Label {
                                text: qsTr("Overview")
                                font.pixelSize: 24
                                font.bold: true
                            }

                            ColumnLayout {
                                visible: gca.repositoryPath.length === 0
                                Layout.fillWidth: true
                                Layout.topMargin: 90
                                spacing: 16

                                Label {
                                    text: qsTr("No repository open")
                                    font.pixelSize: 20
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                Button {
                                    text: qsTr("Choose repository")
                                    onClicked: repositoryDialog.open()
                                    Layout.alignment: Qt.AlignHCenter
                                    Accessible.name: text
                                }

                                Label {
                                    text: qsTr("Recent repositories")
                                    visible: gca.recentRepositories.length > 0
                                    font.bold: true
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                Repeater {
                                    model: gca.recentRepositories
                                    delegate: Button {
                                        required property string modelData
                                        text: modelData
                                        flat: true
                                        Layout.alignment: Qt.AlignHCenter
                                        onClicked: gca.openRepository(modelData)
                                        Accessible.name: qsTr("Open %1").arg(modelData)
                                    }
                                }
                            }

                            RowLayout {
                                visible: gca.repositoryPath.length > 0
                                Layout.fillWidth: true
                                spacing: 0

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Commits"); color: palette.mid }
                                    Label { text: gca.indexedCommits; font.pixelSize: 28; font.bold: true }
                                }
                                Rectangle { width: 1; height: 52; color: palette.midlight }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 20
                                    Label { text: qsTr("People"); color: palette.mid }
                                    Label { text: gca.identityCount; font.pixelSize: 28; font.bold: true }
                                }
                                Rectangle { width: 1; height: 52; color: palette.midlight }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 20
                                    Label { text: qsTr("Unresolved"); color: palette.mid }
                                    Label { text: gca.unresolvedIdentityCount; font.pixelSize: 28; font.bold: true }
                                }
                                Rectangle { width: 1; height: 52; color: palette.midlight }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 20
                                    Label { text: qsTr("Index"); color: palette.mid }
                                    Label { text: gca.indexStatus; font.pixelSize: 18; font.bold: true }
                                }
                            }

                            Rectangle {
                                visible: gca.repositoryPath.length > 0
                                height: 1
                                color: palette.midlight
                                Layout.fillWidth: true
                            }

                            RowLayout {
                                visible: gca.repositoryPath.length > 0
                                spacing: 10

                                Button {
                                    text: qsTr("Initialize")
                                    visible: !gca.workspaceInitialized
                                    enabled: !gca.busy
                                    onClicked: gca.initializeRepository()
                                }
                                Button {
                                    text: qsTr("Sync")
                                    visible: gca.workspaceInitialized
                                    enabled: !gca.busy
                                    onClicked: gca.syncRepository()
                                }
                                Button {
                                    text: qsTr("Rebuild index")
                                    visible: gca.workspaceInitialized
                                    enabled: !gca.busy
                                    onClicked: gca.rebuildIndex()
                                }
                                Button {
                                    text: qsTr("Doctor")
                                    enabled: !gca.busy
                                    onClicked: gca.runDoctor()
                                }
                            }

                            TextArea {
                                visible: gca.currentReportJson.length > 0 && pageIndex === 0
                                text: gca.currentReportJson
                                readOnly: true
                                wrapMode: TextEdit.NoWrap
                                font.family: "monospace"
                                Layout.fillWidth: true
                                Layout.preferredHeight: 300
                            }
                        }
                    }

                    // Structural observations
                    ColumnLayout {
                        spacing: 14
                        Layout.margins: 28

                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                text: qsTr("Structural observations")
                                font.pixelSize: 24
                                font.bold: true
                                Layout.fillWidth: true
                            }
                            Label {
                                text: qsTr("OBSERVATION ONLY")
                                color: palette.highlight
                                font.bold: true
                            }
                            Button {
                                text: qsTr("Refresh")
                                enabled: gca.workspaceInitialized && !gca.busy
                                onClicked: gca.refreshStructural()
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            ColumnLayout {
                                Layout.fillWidth: true
                                Label { text: qsTr("Baselines"); color: palette.mid }
                                Label { text: gca.structuralBaselineCount; font.pixelSize: 24; font.bold: true }
                            }
                            Rectangle { width: 1; height: 46; color: palette.midlight }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 20
                                Label { text: qsTr("Processed commits"); color: palette.mid }
                                Label { text: gca.structuralProcessedCommits; font.pixelSize: 24; font.bold: true }
                            }
                            Rectangle { width: 1; height: 46; color: palette.midlight }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 20
                                Label { text: qsTr("Latest baseline"); color: palette.mid }
                                Label {
                                    text: gca.structuralLatestBaselineId || qsTr("None")
                                    font.family: "monospace"
                                    elide: Text.ElideMiddle
                                    Layout.maximumWidth: 360
                                }
                            }
                        }

                        GridLayout {
                            columns: width < 900 ? 2 : 4
                            columnSpacing: 12
                            rowSpacing: 8
                            Layout.fillWidth: true
                            ColumnLayout {
                                Layout.fillWidth: true
                                Label { text: qsTr("Exclusive cutoff") }
                                TextField { id: structuralCutoff; placeholderText: "2026-07-01T00:00:00Z"; Layout.fillWidth: true }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Label { text: qsTr("Branch") }
                                TextField { id: structuralBranch; placeholderText: qsTr("Configured default"); Layout.fillWidth: true }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Label { text: qsTr("Scope") }
                                TextField { id: structuralScope; placeholderText: qsTr("Entire repository"); Layout.fillWidth: true }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Label { text: qsTr("Time strategy") }
                                ComboBox { id: structuralStrategy; model: ["lifetime", "rolling-window", "dual-window"]; Layout.fillWidth: true }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Button {
                                text: qsTr("Rebuild")
                                enabled: gca.workspaceInitialized && !gca.busy
                                onClicked: gca.rebuildStructural({
                                    cutoff: structuralCutoff.text,
                                    branch: structuralBranch.text,
                                    scope: structuralScope.text,
                                    timeStrategy: structuralStrategy.currentText
                                })
                            }
                            Button {
                                text: qsTr("Show latest")
                                enabled: gca.structuralLatestBaselineId.length > 0 && !gca.busy
                                onClicked: gca.showStructural("")
                            }
                            Item { Layout.fillWidth: true }
                            Label { text: qsTr("Keep") }
                            SpinBox { id: structuralKeep; from: 0; to: 100; value: 8 }
                            Button {
                                text: qsTr("Prune")
                                enabled: gca.structuralBaselineCount > structuralKeep.value && !gca.busy
                                onClicked: structuralPruneConfirm.open()
                            }
                        }

                        SplitView {
                            orientation: Qt.Horizontal
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            ColumnLayout {
                                SplitView.fillWidth: true
                                SplitView.minimumWidth: 300
                                Label { text: qsTr("Hotspots"); font.pixelSize: 18; font.bold: true }
                                TextField { placeholderText: qsTr("Filter hotspots"); onTextChanged: gca.structuralHotspotsModel.set_filter(text); Layout.fillWidth: true }
                                ListView {
                                    model: gca.structuralHotspotsModel
                                    clip: true
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    delegate: Rectangle {
                                        required property var model
                                        width: ListView.view.width
                                        height: 48
                                        color: index % 2 ? palette.alternateBase : palette.base
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            Label { text: model.path || ""; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                            Label { text: model.changeCount || 0; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight }
                                            Label { text: model.confidence || ""; Layout.preferredWidth: 80 }
                                        }
                                    }
                                }
                            }

                            ColumnLayout {
                                SplitView.fillWidth: true
                                SplitView.minimumWidth: 360
                                Label { text: qsTr("Couplings"); font.pixelSize: 18; font.bold: true }
                                TextField { placeholderText: qsTr("Filter couplings"); onTextChanged: gca.structuralCouplingsModel.set_filter(text); Layout.fillWidth: true }
                                ListView {
                                    model: gca.structuralCouplingsModel
                                    clip: true
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    delegate: Rectangle {
                                        required property var model
                                        width: ListView.view.width
                                        height: 56
                                        color: index % 2 ? palette.alternateBase : palette.base
                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 7
                                            Label { text: model.leftPath || ""; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Label { text: model.rightPath || ""; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                                Label { text: qsTr("%1 co-changes").arg(model.coChangeCount || 0); Layout.preferredWidth: 110 }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Dialog {
                            id: structuralPruneConfirm
                            title: qsTr("Prune structural baselines")
                            standardButtons: Dialog.Ok | Dialog.Cancel
                            onAccepted: gca.pruneStructural(structuralKeep.value)
                            Label { text: qsTr("Remove rebuildable baselines beyond the selected retention count?"); wrapMode: Text.WordWrap }
                        }
                    }

                    // Assessment
                    ScrollView {
                        contentWidth: availableWidth

                        ColumnLayout {
                            width: parent.width
                            spacing: 16
                            anchors.margins: 28

                            Label { text: qsTr("Assessment"); font.pixelSize: 24; font.bold: true }

                            GridLayout {
                                columns: width < 820 ? 1 : 2
                                columnSpacing: 18
                                rowSpacing: 12
                                Layout.fillWidth: true

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("People (comma separated)") }
                                    TextField { id: assessPeople; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Exclude people") }
                                    TextField { id: assessExclude; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Since") }
                                    TextField { id: assessSince; placeholderText: "2026-01-01"; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Until") }
                                    TextField { id: assessUntil; placeholderText: "2026-03-31"; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Period") }
                                    ComboBox { id: assessPeriod; model: [qsTr("None"), "week", "month", "quarter"]; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Time basis") }
                                    ComboBox { id: assessTimeBasis; model: ["authored", "committed", "merged", "landed", "released"]; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Branch") }
                                    TextField { id: assessBranch; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Path scope") }
                                    TextField { id: assessScope; Layout.fillWidth: true }
                                }
                            }

                            RowLayout {
                                CheckBox { id: assessAll; text: qsTr("All people") }
                                CheckBox { id: assessLlm; text: qsTr("Use configured LLM"); checked: true }
                                Item { Layout.fillWidth: true }
                                Button {
                                    text: qsTr("Run assessment")
                                    enabled: gca.workspaceInitialized && !gca.busy
                                    onClicked: gca.runAssessment({
                                        persons: splitValues(assessPeople.text),
                                        allPeople: assessAll.checked,
                                        excludePersons: splitValues(assessExclude.text),
                                        since: assessSince.text,
                                        until: assessUntil.text,
                                        period: assessPeriod.currentIndex === 0 ? "" : assessPeriod.currentText,
                                        branch: assessBranch.text,
                                        scope: assessScope.text,
                                        timeBasis: assessTimeBasis.currentText,
                                        useLlm: assessLlm.checked
                                    })
                                }
                            }

                            Rectangle { height: 1; color: palette.midlight; Layout.fillWidth: true }

                            RowLayout {
                                spacing: 28
                                Label { text: qsTr("Run: %1").arg(gca.currentRunId || "-"); font.bold: true }
                                Label { text: qsTr("Completed: %1").arg(gca.completedItems) }
                                Label { text: qsTr("Pending: %1").arg(gca.pendingItems) }
                            }
                        }
                    }

                    // Trends
                    ColumnLayout {
                        spacing: 14
                        Layout.margins: 28
                        Label { text: qsTr("Trends"); font.pixelSize: 24; font.bold: true }
                        Loader {
                            active: gca.chartsEnabled
                            visible: active
                            Layout.fillWidth: true
                            Layout.preferredHeight: active ? 280 : 0
                            sourceComponent: Component {
                                ChartView {
                                    antialiasing: true
                                    legend.alignment: Qt.AlignBottom
                                    backgroundColor: palette.base
                                    plotAreaColor: palette.base

                                    ValueAxis { id: trendXAxis; min: 1; max: 24; tickCount: 7; labelFormat: "%d" }
                                    ValueAxis { id: trendYAxis; min: 0; max: Math.max(10, gca.completedItems + gca.pendingItems); tickCount: 6 }

                                    LineSeries {
                                        id: completedSeries
                                        name: qsTr("Completed")
                                        axisX: trendXAxis
                                        axisY: trendYAxis
                                    }
                                    LineSeries {
                                        id: pendingSeries
                                        name: qsTr("Pending")
                                        axisX: trendXAxis
                                        axisY: trendYAxis
                                    }
                                    VXYModelMapper {
                                        model: gca.trendsModel
                                        series: completedSeries
                                        xColumn: 0
                                        yColumn: 2
                                    }
                                    VXYModelMapper {
                                        model: gca.trendsModel
                                        series: pendingSeries
                                        xColumn: 0
                                        yColumn: 3
                                    }
                                }
                            }
                        }
                        ListView {
                            model: gca.trendsModel
                            clip: true
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 1
                            delegate: Rectangle {
                                required property var model
                                width: ListView.view.width
                                height: 48
                                color: index % 2 ? palette.alternateBase : palette.base
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    Label { text: model.label || ""; Layout.preferredWidth: 180; font.bold: true }
                                    Label { text: qsTr("Completed %1").arg(model.completedItems || 0); Layout.fillWidth: true }
                                    Label { text: qsTr("Pending %1").arg(model.pendingItems || 0); Layout.fillWidth: true }
                                    Label { text: qsTr("Commits %1").arg(model.commits || 0); Layout.fillWidth: true }
                                }
                            }
                        }
                    }

                    // People
                    ColumnLayout {
                        spacing: 14
                        Layout.margins: 28
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: qsTr("People"); font.pixelSize: 24; font.bold: true; Layout.fillWidth: true }
                            Button { text: qsTr("Refresh"); onClicked: gca.refreshIdentities() }
                        }
                        TextField {
                            placeholderText: qsTr("Filter people")
                            onTextChanged: gca.peopleModel.set_filter(text)
                            Layout.fillWidth: true
                        }
                        ListView {
                            model: gca.peopleModel
                            clip: true
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            delegate: Rectangle {
                                required property var model
                                width: ListView.view.width
                                height: 52
                                color: index % 2 ? palette.alternateBase : palette.base
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    Label { text: model.name || ""; font.bold: true; Layout.fillWidth: true }
                                    Label { text: model.email || ""; Layout.fillWidth: true }
                                    Label { text: model.kind || ""; Layout.preferredWidth: 90 }
                                    Label { text: model.confirmed ? qsTr("Confirmed") : qsTr("Unresolved"); Layout.preferredWidth: 100 }
                                }
                            }
                        }
                        RowLayout {
                            TextField { id: aliasName; placeholderText: qsTr("Alias name"); Layout.fillWidth: true }
                            TextField { id: aliasEmail; placeholderText: qsTr("Alias email"); Layout.fillWidth: true }
                            TextField { id: personName; placeholderText: qsTr("Person name"); Layout.fillWidth: true }
                            TextField { id: personEmail; placeholderText: qsTr("Person email"); Layout.fillWidth: true }
                            Button { text: qsTr("Map"); onClicked: gca.mapIdentity(aliasName.text, aliasEmail.text, personName.text, personEmail.text) }
                        }
                        RowLayout {
                            TextField { id: mergeSources; placeholderText: qsTr("Source selectors"); Layout.fillWidth: true }
                            TextField { id: mergeTarget; placeholderText: qsTr("Target selector"); Layout.fillWidth: true }
                            Button { text: qsTr("Preview merge"); onClicked: gca.mergeIdentities(mergeSources.text, mergeTarget.text, true) }
                            Button { text: qsTr("Merge"); onClicked: mergeConfirm.open() }
                        }
                        RowLayout {
                            TextField { id: unmergeId; placeholderText: qsTr("Merge event ID"); Layout.fillWidth: true }
                            Button { text: qsTr("Merge history"); onClicked: gca.listIdentityMerges("ALL") }
                            Button { text: qsTr("Undo merge"); onClicked: gca.unmergeIdentity(unmergeId.text) }
                        }
                        Dialog {
                            id: mergeConfirm
                            title: qsTr("Confirm identity merge")
                            standardButtons: Dialog.Ok | Dialog.Cancel
                            onAccepted: gca.mergeIdentities(mergeSources.text, mergeTarget.text, false)
                            Label { text: qsTr("Merge selected source identities into the target?"); wrapMode: Text.WordWrap }
                        }
                    }

                    // Work items and Evidence
                    SplitView {
                        orientation: Qt.Horizontal

                        ColumnLayout {
                            SplitView.fillWidth: true
                            SplitView.minimumWidth: 280
                            spacing: 10
                            Layout.margins: 20
                            Label { text: qsTr("Work items"); font.pixelSize: 22; font.bold: true }
                            TextField { placeholderText: qsTr("Filter work items"); onTextChanged: gca.workItemsModel.set_filter(text); Layout.fillWidth: true }
                            ListView {
                                model: gca.workItemsModel
                                clip: true
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                delegate: ItemDelegate {
                                    required property var model
                                    width: ListView.view.width
                                    text: (model.title || model.id || "") + "  " + (model.difficulty || "")
                                }
                            }
                        }
                        ColumnLayout {
                            SplitView.fillWidth: true
                            SplitView.minimumWidth: 280
                            spacing: 10
                            Layout.margins: 20
                            Label { text: qsTr("Evidence"); font.pixelSize: 22; font.bold: true }
                            TextField { placeholderText: qsTr("Filter evidence"); onTextChanged: gca.evidenceModel.set_filter(text); Layout.fillWidth: true }
                            ListView {
                                model: gca.evidenceModel
                                clip: true
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                delegate: ItemDelegate {
                                    required property var model
                                    width: ListView.view.width
                                    text: (model.id || "") + "  " + (model.summary || "")
                                }
                            }
                        }
                    }

                    // Runs
                    ColumnLayout {
                        spacing: 12
                        Layout.margins: 28
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: qsTr("Runs"); font.pixelSize: 24; font.bold: true; Layout.fillWidth: true }
                            Button { text: qsTr("Refresh"); onClicked: gca.refreshRuns() }
                        }
                        TextField { placeholderText: qsTr("Filter runs"); onTextChanged: gca.runsModel.set_filter(text); Layout.fillWidth: true }
                        ListView {
                            model: gca.runsModel
                            clip: true
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            delegate: Rectangle {
                                required property var model
                                width: ListView.view.width
                                height: 52
                                color: index % 2 ? palette.alternateBase : palette.base
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    Label { text: model.id || ""; font.family: "monospace"; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Label { text: model.runType || ""; Layout.preferredWidth: 180 }
                                    Label { text: model.status || ""; Layout.preferredWidth: 100 }
                                    Button { text: qsTr("Open"); enabled: model.status === "COMPLETED" || model.status === "PARTIAL"; onClicked: gca.loadRun(model.id) }
                                }
                            }
                        }
                        RowLayout {
                            TextField { id: baseRun; placeholderText: qsTr("Base run ID"); Layout.fillWidth: true }
                            TextField { id: targetRun; placeholderText: qsTr("Target run ID"); Layout.fillWidth: true }
                            Button { text: qsTr("Compare"); onClicked: gca.compareRuns(baseRun.text, targetRun.text) }
                        }
                        RowLayout {
                            TextField { id: exportId; placeholderText: qsTr("Run ID"); text: gca.currentRunId; Layout.fillWidth: true }
                            ComboBox { id: exportType; model: ["markdown", "json", "csv"] }
                            Button {
                                text: qsTr("Export")
                                onClicked: {
                                    exportRunId = exportId.text
                                    exportFormat = exportType.currentText
                                    exportDialog.open()
                                }
                            }
                        }
                        TextArea {
                            text: gca.currentReportJson
                            readOnly: true
                            visible: text.length > 0
                            wrapMode: TextEdit.NoWrap
                            font.family: "monospace"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                        }
                    }

                    // Resume
                    ScrollView {
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: parent.width
                            spacing: 14
                            anchors.margins: 28
                            Label { text: qsTr("Resume"); font.pixelSize: 24; font.bold: true }
                            GridLayout {
                                columns: width < 780 ? 1 : 2
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Person") }
                                    TextField { id: resumePerson; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Target role") }
                                    TextField { id: resumeRole; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Since") }
                                    TextField { id: resumeSince; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Until") }
                                    TextField { id: resumeUntil; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Language") }
                                    ComboBox { id: resumeLanguage; model: ["zh-CN", "en"]; Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Style") }
                                    ComboBox { id: resumeStyle; model: ["concise", "star", "xyz"]; Layout.fillWidth: true }
                                }
                            }
                            RowLayout {
                                CheckBox { id: resumePending; text: qsTr("Include pending") }
                                CheckBox { id: resumeLlm; text: qsTr("Use configured LLM"); checked: true }
                                Item { Layout.fillWidth: true }
                                Button {
                                    text: qsTr("Generate")
                                    enabled: gca.workspaceInitialized && !gca.busy
                                    onClicked: gca.generateResume({
                                        person: resumePerson.text,
                                        targetRole: resumeRole.text,
                                        since: resumeSince.text,
                                        until: resumeUntil.text,
                                        language: resumeLanguage.currentText,
                                        style: resumeStyle.currentText,
                                        includePending: resumePending.checked,
                                        useLlm: resumeLlm.checked
                                    })
                                }
                            }
                            TextArea {
                                text: gca.currentReportJson
                                readOnly: true
                                wrapMode: TextEdit.Wrap
                                font.family: "monospace"
                                Layout.fillWidth: true
                                Layout.preferredHeight: 360
                            }
                        }
                    }

                    // Settings / Providers
                    ColumnLayout {
                        spacing: 14
                        Layout.margins: 28
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: qsTr("Providers"); font.pixelSize: 24; font.bold: true; Layout.fillWidth: true }
                            Button { text: qsTr("Refresh"); onClicked: gca.refreshProviders() }
                            Button { text: qsTr("Test selected"); onClicked: gca.testProvider() }
                        }
                        ListView {
                            model: gca.providersModel
                            clip: true
                            Layout.fillWidth: true
                            Layout.preferredHeight: 280
                            delegate: Rectangle {
                                required property var model
                                width: ListView.view.width
                                height: 48
                                color: index % 2 ? palette.alternateBase : palette.base
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    Label { text: model.id || ""; font.bold: true; Layout.fillWidth: true }
                                    Label { text: model.selected ? qsTr("Selected") : qsTr("Available"); Layout.preferredWidth: 100 }
                                    Label { text: model.localExecution ? qsTr("Local") : qsTr("Remote"); Layout.preferredWidth: 90 }
                                    Label { text: model.requiresApiKey ? qsTr("API key required") : qsTr("No API key"); Layout.preferredWidth: 130 }
                                }
                            }
                        }
                        Rectangle { height: 1; color: palette.midlight; Layout.fillWidth: true }
                        Label { text: qsTr("Recent repositories"); font.pixelSize: 18; font.bold: true }
                        Repeater {
                            model: gca.recentRepositories
                            delegate: Label { required property string modelData; text: modelData; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        }
                        Button { text: qsTr("Clear recent repositories"); onClicked: gca.clearRecentRepositories(); Layout.alignment: Qt.AlignLeft }
                    }
                }

                Label {
                    visible: transientMessage.length > 0
                    text: transientMessage
                    color: palette.highlightedText
                    background: Rectangle { color: palette.highlight; radius: 4 }
                    padding: 10
                    Layout.alignment: Qt.AlignHCenter
                    Layout.bottomMargin: 10
                }
            }
        }
    }
}
