# Copyright 2009 University of Alaska Anchorage Experimental Economics
# Laboratory
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import thread
import time
import webbrowser
import wx

from peet.client import clientnet
from peet.shared.ClientHistory import ClientHistory
from peet.shared.ClientHistoryBook import ClientHistoryBook
from peet.shared.constants import roundingOptions

NetworkEvent, EVT_NETWORK = wx.lib.newevent.NewEvent()

class GameGUI(wx.Frame):

    """Base class for all game interfaces..
    Important: when adding children to this, be sure to make them children of
    self.panel, not self. """

    def __init__(self, communicator, initParams):
        title = 'Game Interface  (' + initParams['name'] + ', id ' +\
                str(initParams['id']) + ')'
        style = wx.CAPTION | wx.CLIP_CHILDREN # | wx.RESIZE_BORDER
        wx.Frame.__init__(self, None, wx.ID_ANY, title, style=style)

        self.communicator = communicator
        self.initParams = initParams
        self.name = initParams['name']
        self.id = initParams['id']

        # Redirect target of network events to this window (was the login
        # window)
        self.communicator.postEvent = self.postNetworkEvent
        self.Bind(EVT_NETWORK, self.onNetworkEvent)

        if self.initParams['type'] == 'reinit':
            self.history = self.initParams.get('history', ClientHistory())
        else:
            self.history = ClientHistory()

        # We always need to put a panel in the frame (because without a panel,
        # the background will be dark gray in Windows).
        self.panel = wx.Panel(self)

        # Need to be able to fit the frame to the panel, and for that we need a
        # sizer (which will only contain the panel).
        #frameSizer = wx.GridBagSizer()
        #self.SetSizer(frameSizer)
        #frameSizer.Add(self.panel, (0,0), flag=wx.EXPAND)
        # Actually, no, we don't: without a sizer, it seems that the panel will
        # resize to fit the frame.

        self.historyBook = ClientHistoryBook(self.panel, self.history,\
                showMatch=initParams.get('showMatch', True))
        self.historyBook.Show(False)
        # To use the historyBook, Add() it to a sizer in the derived class and
        # call historyBook.Show(True)

        # Chat panel
        self.chatPanel = wx.Panel(self.panel)
        self.chatPanel.SetBackgroundColour('white')
        vsizer = wx.BoxSizer(wx.VERTICAL)
        self.chatPanel.SetSizer(vsizer)
        self.chatBox = wx.TextCtrl(self.chatPanel, size=(-1,80),
            #style=wx.TE_MULTILINE|wx.TE_RICH2|wx.TE_READONLY)
            # wxWin BUG: TE_RICH2 causes AppendText to scroll too far
            # However, taking it out means we can't do bold (although we still
            # can in wxGTK).
            style=wx.TE_MULTILINE|wx.TE_READONLY)
        vsizer.Add(self.chatBox, 1, wx.EXPAND)
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.chatEntry = wx.TextCtrl(self.chatPanel, size=(300,-1),
                style=wx.TE_PROCESS_ENTER)
        hsizer.Add(self.chatEntry)
        self.chatSendButton = wx.Button(self.chatPanel, -1, 'Send')
        hsizer.Add(self.chatSendButton)
        vsizer.Add(hsizer)
        self.Bind(wx.EVT_BUTTON, self.onChatSendClicked, self.chatSendButton)
        self.Bind(wx.EVT_TEXT_ENTER, self.onChatSendClicked, self.chatEntry)
        self.chatPanel.Show(False)

    def postNetworkEvent(self, message):
        """ called by the Communicator when something happens.  For thread
        safety, this can't have any gui code, so it just posts an event so an
        event handler function (onNetworkEvent) can respond. """
        event = NetworkEvent(message=message)
        wx.PostEvent(self, event)

    def onNetworkEvent(self, event):
        """ Don't override this method to handle server messages: this does
        anything necessary before passing the message on to the derived class by
        calling onMessageReceived(), which is the one to override. """
        mes = event.message
        if mes['type'] == 'histStartMatch':
            self.historyBook.startMatch(mes['headers'], mes['practice'],\
                    mes['groupID'], mes['stacks'])
        elif mes['type'] == 'histAddRound':
            self.historyBook.addRound(mes['values'])
        elif mes['type'] == 'chat':
            self.chatBox.AppendText(self.makeChatString(mes, mes['id']))
        elif mes['type'] == 'disconnect':
            self.Destroy()
        elif mes['type'] == 'endOfExperiment':
            self.showEndOfExperimentMes(mes)

        self.onMessageReceived(mes)

    def showEndOfExperimentMes(self, mes):
        """ Show window with end of experiment message.  You can override this
        to display a custom message. """

        exchangeRatesEqual = True
        for rate in mes['exchangeRates']:
            if rate != mes['exchangeRates'][0]:
                exchangeRatesEqual = False
                break
        if exchangeRatesEqual:
            rate = mes['exchangeRates'][0]
            rateText = 'The exchange rate is %0.4f.' % rate
        else:
            rate = mes['totalDollarPayoff'] / mes['totalPayoff']
            rateText = 'The average exchange rate on your earnings is %0.4f.'\
                    % rate

        frame = wx.Frame(self, title="End of Experiment",\
                style= wx.CAPTION | wx.CLIP_CHILDREN | wx.FRAME_FLOAT_ON_PARENT)
        panel = wx.Panel(frame)
        panel.SetBackgroundColour('white')
        vsizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(vsizer)
        font =  wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font.SetPointSize(12)
        headingfont =  wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        headingfont.SetPointSize(16)

        heading = wx.StaticText(panel, -1, 'End of Experiment')
        heading.SetFont(headingfont)
        vsizer.Add(heading, flag=wx.ALIGN_CENTER|wx.ALL, border=12)
        roundingString = roundingOptions[mes['rounding']]
        text = 'Your total earnings in experiment currency are %0.2f.\n'\
                % mes['totalPayoff']\
                + '' + rateText + '\n'\
                + 'Your show-up payment is $%0.2f.\n' % mes['showUpPayment']\
                +'Your total earnings in US dollars, rounded %s, are $%0.2f.\n'\
                % (roundingString, mes['totalDollarPayoff'])
        if mes.get('survey', False):
            text += 'Please click on the button below to take a short survey.'
        else:
            text += 'Please wait quietly for your name to be called\n'\
                'as we count your earnings.\n'\
                '\n'\
                'Thank you for participating.'
        textlabel = wx.StaticText(panel, -1, text)
        textlabel.SetFont(font)
        vsizer.Add(textlabel, flag=wx.ALIGN_CENTER|wx.ALL, border=12)

        if mes.get('survey', False):
            button = wx.Button(panel, -1, 'Take Survey')
            vsizer.Add(button, flag=wx.ALIGN_CENTER|wx.ALL, border=12)
            self.Bind(wx.EVT_BUTTON, self.onSurveyClicked, button)

        vsizer.Fit(frame)
        frame.Centre()
        frame.Show(True)

    def onSurveyClicked(self, event):
        # FIXME don't hardcode
        webbrowser.open_new('http://' + self.communicator.address\
                + ':9124/survey%d.html' % self.id)

    def onMessageReceived(self, mes):
        """ Override this method to handle server messages. """
        print "server said: " + str(mes)

    def sendReadyMessage(self):
        """ Inform the server that the GUI is ready for the game to begin.
        Called by the login window for convenience; it's the one that creates
        the GameGUI. """
        self.communicator.send({'type': 'ready'})
        print 'sendReadyMessage(): done'

    def makeChatString(self, mes, id):
        return '\nPlayer ' + str(id) + ': ' + mes['message']

    def onChatSendClicked(self, event):
        mes = {'type': 'chat', 'message': self.chatEntry.GetValue() }
        self.chatEntry.SetValue('')
        style = self.chatBox.GetDefaultStyle()
        font = style.GetFont()
        font.SetWeight(wx.BOLD)
        style.SetFont(font)
        self.chatBox.SetDefaultStyle(style)
        self.chatBox.AppendText(self.makeChatString(mes, self.id))
        font.SetWeight(wx.NORMAL)
        style.SetFont(font)
        self.chatBox.SetDefaultStyle(style)
        self.communicator.send(mes)
