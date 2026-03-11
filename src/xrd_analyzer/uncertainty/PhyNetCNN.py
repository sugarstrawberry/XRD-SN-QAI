import torch
import torch.nn as nn
import torch.nn.functional as F


class Model(nn.Module):
    def __init__(self, raw_xrd_length=3501, physical_features_length=45, num_classes=230):
        super(Model, self).__init__()
        # self.resnet = PXRDResNet(ResidualBlock, [1, 2, 2, 1])
        self.cnn_branch = nn.Sequential(
                nn.Conv1d(1, 40, 100, 5),
                nn.BatchNorm1d(40),
                nn.ReLU(),
                nn.Dropout(0.4),
                nn.Conv1d(40, 80, 50, 5),
                nn.BatchNorm1d(80),
                nn.ReLU(),
                nn.Dropout(0.4),
                nn.Conv1d(80, 80, 25, 2),
                nn.BatchNorm1d(80),
                nn.ReLU(),
                nn.Dropout(0.4),
                # nn.AdaptiveAvgPool1d(1) 
            )

        self.gate_xrd_projector = nn.Linear(12160, 128)

        self.mlp_branch = nn.Sequential(
            nn.Linear(physical_features_length, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU()
        )

        self.gating_network = nn.Sequential(
            nn.Linear(12160 + 64, 128), 
            nn.ReLU(),
            nn.Linear(128, 1), 
            nn.Sigmoid()   
        )

        self.classifier_head = nn.Sequential(
            nn.Linear(12160 + 64, 2300),nn.ReLU(),nn.Dropout(0.5),
            nn.Linear(2300, 1150), nn.ReLU(), nn.Dropout(0.5),
            nn.Linear(1150, num_classes)
        )

    def forward(self, x_xrd, x_phys):
        x_xrd = x_xrd.unsqueeze(1) 
        x_xrd = F.interpolate(x_xrd,size=8500,mode='linear', align_corners=False)
        xrd_features = self.cnn_branch(x_xrd)
        # xrd_features = self.resnet(x_xrd)

        xrd_features = xrd_features.reshape(xrd_features.shape[0], -1)

        phys_features = self.mlp_branch(x_phys)

        gate_input = torch.cat((xrd_features, phys_features), dim=1)
        g = self.gating_network(gate_input)
        
        gated_xrd_features = g * xrd_features
        gated_phys_features = (1.0 - g) * phys_features

        merged = torch.cat((gated_xrd_features, gated_phys_features), dim=1)
        output_logits = self.classifier_head(merged)
        
        # output_logits = self.classifier_head(xrd_features)
        return output_logits
