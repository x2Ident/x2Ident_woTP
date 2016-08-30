import React, { PropTypes, Component } from 'react'
import { connect } from 'react-redux'

import { startEdit, stopEdit } from '../../ducks/ui/flow'

ToggleEdit.propTypes = {
    isEdit: PropTypes.bool.isRequired,
    flow: PropTypes.object.isRequired,
    startEdit: PropTypes.func.isRequired,
    stopEdit: PropTypes.func.isRequired,
}

function ToggleEdit({ isEdit, startEdit, stopEdit, flow, modifiedFlow }) {
    return (
        <div className="edit-flow-container">
            {isEdit ?
                <a className="edit-flow" onClick={() => stopEdit(flow, modifiedFlow)}>
                    <i className="fa fa-check"/>
                </a>
                :
                <a className="edit-flow" onClick={() => startEdit(flow)}>
                    <i className="fa fa-pencil"/>
                </a>
            }
        </div>
    )
}

export default connect(
    state => ({
        isEdit: !!state.ui.flow.modifiedFlow,
        modifiedFlow: state.ui.flow.modifiedFlow || state.flows.byId[state.flows.selected[0]],
        flow: state.flows.byId[state.flows.selected[0]]
    }),
    {
        startEdit,
        stopEdit,
    }
)(ToggleEdit)
